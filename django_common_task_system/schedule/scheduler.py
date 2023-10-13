from django.conf import settings
from django_common_task_system.choices import ScheduleStatus
from django_common_task_system.builtins import builtins
from django_common_task_system import get_schedule_model, get_schedule_serializer
from django_common_task_system.models import AbstractSchedule
from django_common_task_system.utils.logger import add_file_handler
from django_common_task_system.cache_service import cache_agent
from django_common_task_system.program import Program, ProgramAgent, ProgramState
from .config import ScheduleConfig
from datetime import datetime
from typing import Callable
import time
import logging
import threading
import os


logger = logging.getLogger('schedule')
Schedule: AbstractSchedule = get_schedule_model()
ScheduleSerializer = get_schedule_serializer()


class SchedulerState(ProgramState):
    def __init__(self, key):
        super(SchedulerState, self).__init__(key)
        # self.key = key
        # self.ident = None
        # self.name = None
        self.scheduled_count = 0
        self.last_schedule_time = ''
        self.log_file = ''
        # self.is_running = False

    def json(self):
        return dict(
            ident=self.ident,
            name=self.engine,
            scheduled_count=self.scheduled_count,
            last_schedule_time=self.last_schedule_time,
            log_file=self.log_file,
            is_running=self.is_running
        )


class Scheduler(Program):
    _event = threading.Event()
    # log_file = add_file_handler(logger)
    # key = 'scheduler'
    # state = SchedulerState(key)
    # name = 'Scheduler'
    state_class = SchedulerState
    state_key = 'scheduler'

    def __init__(self):
        super(Scheduler, self).__init__(name='Scheduler')
        self.log_file = add_file_handler(self.logger)

    def init_state(self, **kwargs):
        super(Scheduler, self).init_state(
            log_file=self.log_file,
        )

    @property
    def program_id(self) -> int:
        return os.getpid()

    def produce(self):
        state = self.state
        count = 0
        now = datetime.now()
        qsize = getattr(settings, 'SCHEDULE_QUEUE_MAX_SIZE', 1000)
        max_queue_size = qsize * 2
        schedule_result = {}
        for producer in builtins.schedule_producers.values():
            queue_instance = builtins.schedule_queues[producer.queue.code]
            queue = queue_instance.queue
            before_size = queue.qsize()
            # 队列长度大于1000时不再生产, 防止内存溢出
            if before_size >= qsize:
                logger.info('queue %s is full(%s), skip schedule' % (queue_instance.code, qsize))
                continue
            queryset = Schedule.objects.filter(**producer.filters).select_related(
                'task', 'task__category', 'task__parent')
            if producer.lte_now:
                queryset = queryset.filter(next_schedule_time__lte=now)
            for schedule in queryset:
                try:
                    # 限制队列长度, 防止内存溢出
                    while queue.qsize() < max_queue_size and schedule.next_schedule_time <= now:
                        schedule.queue = queue_instance.code
                        data = ScheduleSerializer(schedule).data
                        queue.put(data)
                        schedule.next_schedule_time = ScheduleConfig(
                            config=schedule.config
                        ).get_next_time(schedule.next_schedule_time)
                    schedule.save(update_fields=('next_schedule_time', ))
                except Exception as e:
                    schedule.status = ScheduleStatus.ERROR.value
                    schedule.save(update_fields=('status',))
                    raise e
            put_size = queue.qsize() - before_size
            schedule_result[queue_instance.code] = put_size
            # 诡异的是这里的scheduled_count运行几次后还会变成0, 为什么?
            count += put_size
        state.last_schedule_time = now.strftime('%Y-%m-%d %H:%M:%S')
        for queue_code, put_size in schedule_result.items():
            logger.info('schedule %s schedules to %s' % (put_size, queue_code))
        state.scheduled_count += count
        state.update()
        # # 设置schedule-thread:pid的过期时间为5秒, 5秒后如果没有更新, 则认为该进程已经停止, 此set相当于心跳包
        # cache_agent.set('schedule-thread:pid', self.runner_id, expire=5)
        # 设置schedule-thread的状态, 用于监控, 不用以下设置为心跳, 是因为想保留上次的状态

    def run(self) -> None:
        add_file_handler(logger, self.log_file)
        # 等待系统初始化完成, 5秒后自动开始
        self._event.wait(timeout=5)
        self._event.set()
        SCHEDULE_INTERVAL = getattr(settings, 'SCHEDULE_INTERVAL', 1)
        is_set = self._event.is_set
        while is_set():
            try:
                self.produce()
            except Exception as e:
                logger.exception(e)
            time.sleep(SCHEDULE_INTERVAL)

    # def start_if_not_started(self):
    #     start: Callable[[], None] = getattr(self, 'start', None)
    #     assert start, 'runner must have start method'
    #     if self.state.is_running:
    #         error = 'schedule thread already started, pid: %s' % self.state.ident
    #     else:
    #         start()
    #         self.state.update(ident=self.runner_id, log_file=self.log_file,
    #                           runner=self.__class__.__name__, is_running=True, name=self.name)
    #         logger.info('schedule thread started, pid: %s' % self.runner_id)
    #         error = ''
    #     logger.info(error)
    #     return error

    def stop(self):
        self._event.clear()


class SchedulerThread(Scheduler, threading.Thread):
    def __init__(self):
        super().__init__()
        threading.Thread.__init__(self, daemon=True, name=self.program_name)

    @property
    def program_id(self) -> int:
        return self.ident

    def stop(self):
        super(SchedulerThread, self).stop()
        while self.is_alive():
            time.sleep(0.5)


# class SchedulerAgent:
#     def __init__(self, schedule_class=SchedulerThread):
#         self._scheduler_class = schedule_class
#         self._scheduler: Scheduler = schedule_class()
#         self._lock = threading.Lock()
#
#     @property
#     def is_running(self):
#         return self._scheduler.is_running
#
#     @property
#     def state(self):
#         return self._scheduler.state
#
#     def start(self):
#         return self._scheduler.start_if_not_started()
#
#     def stop(self):
#         if self._scheduler is None or not self.state.is_running:
#             error = 'schedule thread not started'
#         else:
#             if not self._lock.acquire(blocking=False):
#                 error = 'another action to thread is processing'
#             else:
#                 error = self.stop()
#                 self._scheduler = self._scheduler_class()
#                 self._lock.release()
#
#         return error
#
#     def restart(self):
#         error = self.stop()
#         if not error:
#             error = self.start()
#         return error


scheduler_agent = ProgramAgent(program_class=SchedulerThread)
