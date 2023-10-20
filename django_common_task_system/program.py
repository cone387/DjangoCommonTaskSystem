import json
import threading
import logging
import enum
import os
from typing import Callable, Optional, Union, List, Dict
from docker.models.containers import Container
from django_common_task_system.cache_service import cache_agent
from django_common_task_system.choices import ContainerStatus
from django_common_task_system.utils.logger import add_file_handler
from django_common_task_system.log import PagedLog


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


class RemoteContainer(Container):
    def __init__(self, attrs):
        super(RemoteContainer, self).__init__(attrs)

    def start(self, **kwargs):
        pass

    def stop(self, **kwargs):
        pass

    def restart(self, **kwargs):
        pass

    def logs(self, **kwargs):
        return ''

    def remove(self, **kwargs):
        pass


class Key(str):
    pass


class MapKey(str):
    pass


class ListKey(str):
    pass


class ProgramState(dict):
    def __init__(self, key: Union[MapKey, Key]):
        super(ProgramState, self).__init__()
        self.key = key
        self.ident = None
        self.is_running = False
        self.engine = None
        self.create_time = None
        self.program_name = None
        self.program_class = None
        self.container = None

    def __setattr__(self, key, value):
        self[key] = value
        super(ProgramState, self).__setattr__(key, value)

    def commit(self, **kwargs) -> dict:
        for k, v in kwargs.items():
            setattr(self, k, v)
        return kwargs or self

    def push(self, **kwargs):
        if isinstance(self.key, Key):
            cache_agent.hset(self.key, mapping=kwargs)
        else:
            cache_agent.hset(self.key, self.ident, json.dumps(kwargs))

    def commit_and_push(self, **kwargs):
        if isinstance(self.key, Key):
            return self.push(**self.commit(**kwargs))
        else:
            self.commit(**kwargs)
            return self.push(**self)

    def pull(self):
        if isinstance(self.key, Key):
            state = cache_agent.hgetall(self.key)
        else:
            state = cache_agent.hget(self.key, self.ident)
            if state:
                state = json.loads(state)
        if state:
            for k, v in state.items():
                setattr(self, k, v)

    def delete(self):
        if isinstance(self.key, Key):
            cache_agent.delete(self.key)
        else:
            cache_agent.hdel(self.key, self.ident)


class ContainerState(dict):
    def __init__(self, container: Container = None, state: Dict = None):
        super(ContainerState, self).__init__()
        assert container or state, 'container or state must be set'
        if container:
            config = container.attrs['Config']
            self.name = container.name
            self.id = container.id
            self.short_id = container.short_id
            self.status = container.status
            self.environment = config['Env']
            self.command = config['Cmd']
            self.image = config['Image']
            self.volume = config['Volumes']
            self.create_time = container.attrs['Created']
        else:
            for k, v in state.items():
                setattr(self, k, v)

    def __setattr__(self, key, value):
        self[key] = value
        super(ContainerState, self).__setattr__(key, value)

    def to_attrs(self):
        return {
            'Id': self.id,
            'Created': self.create_time,
            'State': {
                'Status': self.status,
            },
            'Config': {
                'Image': self.image,
                'Cmd': self.command,
                'Env': self.environment,
                'Volumes': self.volume,
            },
        }

    def to_container(self):
        return RemoteContainer(self.to_attrs())


class Program:
    state_class = ProgramState
    state_key: Key = None

    def __init__(self, name=None, container=None, logger: logging.Logger = None):
        assert isinstance(self.state_key, (Key, MapKey, ListKey)), \
            '%s.state_key type must be (Key, MapKey, ListKey), current is %s' % (
                self.__class__.__name__, self.state_key)
        self._event = threading.Event()
        self.state = self.state_class(self.state_key)
        self.container: Optional[Container, RemoteContainer] = container
        self._program_name = name
        self._logger = logger
        self._log_file = None

    @classmethod
    def load_from_state(cls, state: dict):
        container_state = state.pop('container', None)
        if container_state:
            container = ContainerState(state=container_state).to_container()
        else:
            container = None
        program_class = state.pop('program_class', None)
        package, program_class = program_class.rsplit('.', 1)
        program_package = __import__(package, fromlist=[program_class])
        program_class = getattr(program_package, program_class)
        program = program_class(container=container)
        return program

    @property
    def program_name(self):
        if self._program_name:
            name = self._program_name
        elif self.container is not None:
            name = self.container.name
        else:
            name = self.__class__.__name__
        return name

    @property
    def log_file(self):
        if self._log_file is None:
            _ = self.logger
        return self._log_file

    @property
    def logger(self):
        if self._logger is None:
            self._logger = logging.getLogger(self.program_name)
        if self._log_file is None:
            self._log_file = add_file_handler(self._logger)
        return self._logger

    @property
    def is_running(self):
        return self.state.is_running

    @property
    def program_id(self) -> int:
        return os.getpid()

    def pre_started(self):
        self.state.commit_and_push(
            program_name=self.program_name,
            is_running=False,
            engine=self.__class__.__name__,
            program_class=self.__class__.__module__ + '.' + self.__class__.__name__,
        )

    def on_started(self):
        if self.container:
            self.state.commit_and_push(
                container=ContainerState(self.container),
                is_running=self.container.status == ContainerStatus.RUNNING.lower(),
                ident=self.program_id
            )
        else:
            self.state.commit_and_push(
                is_running=True,
                ident=self.program_id
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
            self.pre_started()
            start_program()
            self.on_started()
            self.logger.info('%s started, pid: %s' % (self, self.program_id))
            error = ''
        self.logger.info(error)
        return error

    def stop(self, destroy=False):
        self._event.clear()
        if self.container:
            self.container.stop()
            if destroy:
                self.container.remove()
        if destroy:
            self.state.delete()
        else:
            self.state.commit_and_push(
                is_running=False,
            )

    def read_log(self, page=0, page_size=10):
        if self.container:
            return self.container.logs(tail=page_size)
        else:
            return PagedLog(self.log_file, page_size=page_size).read_page(page=page)

    def __str__(self):
        return "Program(%s)" % self.__class__.__name__


class LocalProgram(Program):

    def run(self) -> None:
        raise NotImplementedError

    def pre_started(self):
        self.state.commit_and_push(
            name=self.program_name,
            is_running=False,
            engine=self.__class__.__name__,
            log_file=self.log_file
        )


class ProgramManager:
    default_state_key = 'programs'

    def __init__(self, key: Union[MapKey, str] = None, program_class=None):
        if key is None:
            key = program_class.state_key
        if not key:
            key = self.default_state_key
        if isinstance(key, str):
            key = MapKey(key)
        assert isinstance(program_class.state_key, MapKey), 'state_key type must be MapKey'
        self.state_key = key

    def all(self) -> List[Program]:
        programs = cache_agent.hgetall(self.state_key)
        if programs:
            return [Program.load_from_state(json.loads(program)) for program in programs.values()]
        else:
            return []

    def get(self, program_id) -> Optional[Program]:
        program = cache_agent.hget(self.state_key, program_id)
        if program:
            return Program.load_from_state(json.loads(program))

    def add(self, program: Program) -> None:
        program.state.push()

#
# class ContainerProgram(Program):
#     def __init__(self, container=None):
#         self.container: Optional[Container, RemoteContainer] = container
#         super().__init__(name=getattr(container, 'name', None))
#
#     def run(self) -> None:
#         raise NotImplementedError
#
#     def read_log(self, page=0, page_size=1000):
#         if self.container:
#             return self.container.logs(tail=page_size)
#
#     # def start(self):
#     #     self.container.start()
#     #
#     def stop(self):
#         assert self.container, 'container must be set'
#         self.container.stop()
#         self.container.remove()
#
#     def restart(self):
#         self.container.restart()
#
#     @property
#     def is_running(self):
#         return self.container.status == ContainerStatus.RUNNING


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
