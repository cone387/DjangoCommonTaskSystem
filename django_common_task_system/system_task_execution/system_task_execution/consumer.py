import os
import traceback
import socket
import logging
from queue import Queue
from typing import Callable
from django_common_task_system.models import ExceptionReport
from django_common_task_system import get_schedule_log_model
from django_common_task_system.choices import ExecuteStatus
from django_common_task_system.cache_service import cache_agent
from django_common_task_system.program import Program, ProgramState
from django_common_task_system.utils.logger import add_file_handler
from datetime import datetime


IP = socket.gethostbyname(socket.gethostname())
logger = logging.getLogger('consume')
ScheduleLog = get_schedule_log_model()


class NoRetryException(Exception):
    """
    预期之内的异常，不需要重试
    """
    @property
    def status(self):
        return ExecuteStatus.NO_RETRY.value


class EmptyResult(Exception):

    @property
    def status(self):
        return ExecuteStatus.EMPTY.value


class PartialFailed(Exception):

    @property
    def status(self):
        return ExecuteStatus.PARTIAL_FAILED.value


class Failed(Exception):

    @property
    def status(self):
        return ExecuteStatus.FAILED.value


class Category:
    def __init__(self, category):
        self.name = category['name']
        self.parent = Category(category['parent']) if category.get('parent') else None
        self.config = category.get('config') or {}


class Task:

    def __init__(self, task):
        self.id = task['id']
        self.name = task['name']
        self.category = Category(task['category']) if task.get('category') else None
        self.config = task.get('config') or {}
        self.parent = Task(task['parent']) if task.get('parent') else None
        self.content = task

    def __str__(self):
        return 'Task(id=%s, name=%s)' % (self.id, self.name)

    __repr__ = __str__


class Schedule:

    def __init__(self, schedule):
        self.id = schedule['id']
        self.schedule_time = datetime.strptime(schedule['schedule_time'], '%Y-%m-%d %H:%M:%S')
        self.callback = schedule['callback']
        self.task = Task(schedule['task'])
        self.queue = schedule.get('queue', None)
        self.config = schedule.get('config') or {}
        self.generator = schedule.get('generator', None)
        self.last_log = schedule.get('last_log', None)
        self.preserve_log = schedule.get('preserve_log', True)
        self.content = schedule

    def __str__(self):
        return 'Schedule(id=%s, time=%s, task=%s)' % (
            self.id, self.schedule_time, self.task
        )

    __repr__ = __str__

    def __hash__(self):
        return hash("%s-%s" % (self.id, self.schedule_time))


class BaseExecutor(object):
    parent = None
    name = None

    def __init__(self, schedule: Schedule):
        self.schedule = schedule

    def execute(self):
        raise NotImplementedError

    def start(self):
        log = ScheduleLog(schedule_id=self.schedule.id,
                          result={'generator': self.schedule.generator},
                          status=ExecuteStatus.SUCCEED.value, queue=self.schedule.queue,
                          schedule_time=self.schedule.schedule_time
                          )
        try:
            log.result['result'] = self.execute()
        except EmptyResult as e:
            if hasattr(e, 'status'):
                log.status = e.status
                log.result['msg'] = str(e)
            else:
                log.status = ExecuteStatus.EXCEPTION
                log.result['msg'] = traceback.format_exc()
        try:
            log.save()
        except Exception as e:
            logger.exception(e)


class _Executor(dict):

    def __call__(self, schedule: Schedule) -> BaseExecutor:
        try:
            executor = self[schedule.task.name]
        except KeyError:
            executor = self[schedule.task.parent.name]
        return executor(schedule)

    def register(self, func_or_class: BaseExecutor):
        if func_or_class.name:
            self[func_or_class.name] = func_or_class
        elif func_or_class.parent:
            self[func_or_class.parent] = func_or_class
        else:
            raise ValueError('Executor must have name or parent')
        return func_or_class


Executor = _Executor()


def load_executors(module_path='django_common_task_system.system_task_execution.system_task_execution.executors'):
    import importlib
    from pathlib import Path
    try:
        module = importlib.import_module(module_path)
    except ImportError:
        logger.exception('import module %s failed' % module_path)
        return
    if not hasattr(module, '__loaded__'):
        module_file = Path(module.__file__)
        if module_file.name == "__init__.py":
            package = module_file.parent
            for p in package.glob('*'):
                if (p.is_dir() and (p / '__init__.py').exists()) or \
                        (p.suffix == '.py' and (not p.stem.startswith('_'))):
                    load_executors(module_path + '.' + p.stem)
    module.__loaded__ = True


class ConsumerState(ProgramState):
    def __init__(self, key):
        super(ConsumerState, self).__init__(key)
        # self.key = key
        # self.ident = None
        # self.name = None
        self.succeed_count = 0
        self.failed_count = 0
        self.last_process_time = ''
        self.log_file = ''
        # self.is_running = False

    def json(self):
        return dict(
            ident=self.ident,
            name=self.engine,
            succeed_count=self.succeed_count,
            failed_count=self.failed_count,
            last_process_time=self.last_process_time,
            log_file=self.log_file,
            is_running=self.is_running
        )

    # def update(self, **kwargs):
    #     if not kwargs:
    #         kwargs = dict(
    #             ident=self.ident,
    #             succeed_count=self.succeed_count,
    #             failed_count=self.failed_count,
    #             last_process_time=self.last_process_time,
    #             is_running=self.is_running
    #         )
    #     else:
    #         for k, v in kwargs.items():
    #             setattr(self, k, v)
    #     try:
    #         cache_agent.hset(self.key, mapping=kwargs)
    #     except Exception as e:
    #         logger.exception(e)
    #
    # def pull(self):
    #     try:
    #         state = cache_agent.hgetall(self.key)
    #         for k, v in state.items():
    #             setattr(self, k, v)
    #     except Exception as e:
    #         logger.exception(e)


class Consumer(Program):
    # key = 'consumer'
    # log_file = add_file_handler(logger)
    # state = ConsumerState(key)
    # name = 'Consumer'
    state_class = ConsumerState
    state_key = 'consumer'

    def __init__(self, queue: Queue):
        super(Consumer, self).__init__(name='Consumer')
        self.queue = queue
        self.log_file = add_file_handler(self.logger)

    # @property
    # def id(self):
    #     return os.getpid()
    #
    # @property
    # def is_running(self):
    #     return self.state.is_running

    def init_state(self):
        super(Consumer, self).init_state(
            log_file=self.log_file,
        )

    @property
    def program_id(self) -> int:
        return os.getpid()

    def run(self):
        queue = self.queue
        state = self.state
        load_executors()
        logger.info('system schedule execution process started')
        while True:
            state.update()
            try:
                schedule = queue.get()
                schedule = Schedule(schedule)
                logger.info('get schedule: %s', schedule)
                executor = Executor(schedule)
                executor.start()
                state.succeed_count += 1
            except Exception as e:
                state.failed_count += 1
                logger.exception(e)
                try:
                    ExceptionReport.objects.create(
                        ip=IP,
                        content=traceback.format_exc(),
                    )
                except Exception as e:
                    logger.exception(e)
            finally:
                state.last_process_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # def start_if_not_started(self):
    #     start: Callable[[], None] = getattr(self, 'start', None)
    #     assert start, 'runner must have start method'
    #     if self.state.is_running:
    #         error = 'execution thread already started, pid: %s' % self.state.ident
    #         logger.info(error)
    #     else:
    #         start()
    #         self.state.update(ident=self.id, log_file=self.log_file,
    #                           runner=self.__class__.__name__, is_running=True, name=self.name)
    #         logger.info('execution thread started, pid: %s' % self.id)
    #         error = ''
    #     return error

    def stop(self):
        raise NotImplementedError


def consume(queue):
    consumer = Consumer(queue)
    consumer.run()


# class ConsumerAgent:
#     def __init__(self, consumer_class):
#         self._consumer_class = consumer_class
#         self._consumer: Consumer = consumer_class()
#         self._lock = threading.Lock()
#
#     @property
#     def is_running(self):
#         return self._consumer.is_running
#
#     @property
#     def state(self):
#         return self._consumer.state
#
#     def start(self):
#         return self._consumer.start_if_not_started()
#
#     def stop(self):
#         if not self.state.is_running:
#             error = 'consumer not started'
#         else:
#             if not self._lock.acquire(blocking=False):
#                 error = 'another action to consumer is processing'
#             else:
#                 error = self._consumer.stop()
#                 self._consumer = self._consumer_class()
#                 self._lock.release()
#         return error
#
#     def restart(self):
#         error = self.stop()
#         if not error:
#             error = self.start()
#         return error
