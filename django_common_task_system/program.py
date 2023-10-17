import threading
import logging
import enum
import os
from typing import Callable, Optional
from docker.models.containers import Container
from django_common_task_system.cache_service import cache_agent
from django_common_task_system.choices import ContainerStatus


class ProgramAction(str, enum.Enum):
    START = 'start'
    STOP = 'stop'
    RESTART = 'restart'
    LOG = 'log'


class ContainerProgramAction(str, enum.Enum):
    START = 'start'
    STOP = 'stop'
    RESTART = 'restart'
    LOG = 'log'
    DESTROY = 'destroy'


class ProgramState(dict):
    def __init__(self, key):
        super(ProgramState, self).__init__()
        self.key = key
        self.ident = None
        self.is_running = False
        self.engine = None
        self.create_time = None

    def __setattr__(self, key, value):
        self[key] = value
        super(ProgramState, self).__setattr__(key, value)

    def commit(self, **kwargs) -> dict:
        for k, v in kwargs.items():
            setattr(self, k, v)
        return kwargs or self

    def push(self, **kwargs):
        cache_agent.hset(self.key, mapping=kwargs)

    def commit_and_push(self, **kwargs):
        return self.push(**self.commit(**kwargs))

    def pull(self):
        state = cache_agent.hgetall(self.key)
        for k, v in state.items():
            setattr(self, k, v)


class Program:
    state_class = ProgramState
    state_key = ''

    def __init__(self, name=None, logger: logging.Logger = None):
        assert self.state_key, 'state_key must be set'
        self._event = threading.Event()
        self.state = self.state_class(self.state_key)
        self.program_name = name or self.__class__.__name__
        self.logger = logger or logging.getLogger(self.program_name.lower())

    @property
    def is_running(self):
        return self.state.is_running

    @property
    def program_id(self) -> int:
        return os.getpid()

    def init_state(self, **kwargs):
        self.state.commit_and_push(
            name=self.program_name,
            is_running=False,
            engine=self.__class__.__name__,
            **kwargs
        )

    def run(self) -> None:
        raise NotImplementedError

    def start_if_not_started(self) -> str:
        start_program: Callable[[], None] = getattr(self, 'start', None)
        if start_program is None:
            start_program = getattr(self, 'run', None)
        assert start_program, 'start or run method must be implemented'
        if self.is_running:
            error = '%s already started, pid: %s' % (self, self.program_id)
        else:
            self.init_state()
            start_program()
            self.state.commit_and_push(is_running=True, ident=self.program_id)
            self.logger.info('%s started, pid: %s' % (self, self.program_id))
            error = ''
        self.logger.info(error)
        return error

    def stop(self):
        self._event.clear()

    def read_log(self, page=0, page_size=10):
        raise NotImplementedError

    def __str__(self):
        return "Program(%s)" % self.__class__.__name__


class ContainerProgram(Program):
    def __init__(self, container=None):
        self.container: Optional[Container] = container
        super().__init__(name=getattr(container, 'name', None))

    def run(self) -> None:
        raise NotImplementedError

    def read_log(self, page=0, page_size=1000):
        if self.container:
            return self.container.logs(tail=page_size)

    # def start(self):
    #     self.container.start()
    #
    def stop(self):
        assert self.container, 'container must be set'
        self.container.stop()
        self.container.remove()

    def restart(self):
        self.container.restart()

    @property
    def is_running(self):
        return self.container.status == ContainerStatus.RUNNING


class ProgramAgent:
    def __init__(self, program_class):
        self._program_class = program_class
        self._program: Program = program_class()
        self._lock = threading.Lock()

    @property
    def is_running(self):
        return self._program.is_running

    @property
    def state(self):
        return self._program.state

    def start(self) -> str:
        if self._lock.acquire(blocking=False):
            error = self._program.start_if_not_started()
            self._lock.release()
        else:
            error = 'another action to %s is processing' % self._program
        return error

    def stop(self) -> str:
        if not self.is_running:
            error = '%s have not started' % self._program
        else:
            if self._lock.acquire(blocking=False):
                error = self._program.stop()
                self.state.commit_and_push(
                    is_running=False,
                    ident=None
                )
                self._program = self._program_class()
                self._lock.release()
            else:
                error = 'another action to %s is processing' % self._program
        return error

    def restart(self) -> str:
        error = self.stop()
        if not error:
            error = self.start()
        return error
