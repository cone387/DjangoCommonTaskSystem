import threading
import logging
from typing import Callable
from django_common_task_system.cache_service import cache_agent


logger = logging.getLogger('program')


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
        try:
            cache_agent.hset(self.key, mapping=kwargs)
        except Exception as e:
            logger.exception(e)

    def commit_and_push(self, **kwargs):
        return self.push(**self.commit(**kwargs))

    def pull(self):
        try:
            state = cache_agent.hgetall(self.key)
            for k, v in state.items():
                setattr(self, k, v)
        except Exception as e:
            logger.exception(e)


class Program:
    state_class = ProgramState
    state_key = ''

    def __init__(self, name=None):
        assert self.state_key, 'state_key must be set'
        self.state = self.state_class(self.state_key)
        self.program_name = name or self.__class__.__name__
        self.logger = logging.getLogger(self.program_name.lower())

    @property
    def is_running(self):
        return self.state.is_running

    @property
    def program_id(self) -> int:
        raise NotImplementedError

    def init_state(self, **kwargs):
        self.state.commit_and_push(
            name=self.program_name,
            is_running=False,
            engine=self.__class__.__name__,
            **kwargs
        )

    def start_if_not_started(self) -> str:
        start_program: Callable[[], None] = getattr(self, 'start', None)
        assert start_program, '%s must have start method' % self
        if self.is_running:
            error = '%s already started, pid: %s' % (self, self.program_id)
        else:
            self.init_state()
            start_program()
            self.state.commit_and_push(is_running=True, ident=self.program_id)
            logger.info('%s started, pid: %s' % (self, self.program_id))
            error = ''
        logger.info(error)
        return error

    def stop(self) -> str:
        raise NotImplementedError

    def __str__(self):
        return "Program(%s)" % self.__class__.__name__


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
            error = 'another action to Program(%s) is processing' % self._program_class.__name__
        return error

    def stop(self) -> str:
        if not self.is_running:
            error = 'Program(%s) have not started' % self._program_class.__name__
        else:
            if not self._lock.acquire(blocking=False):
                error = 'another action to Program(%s) is processing' % self._program_class.__name__
            else:
                error = self.stop()
                self._program = self._program_class()
                self._lock.release()
        return error

    def restart(self) -> str:
        error = self.stop()
        if not error:
            error = self.start()
        return error
