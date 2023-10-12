from django.conf import settings
from django_common_task_system.choices import ScheduleStatus
from django_common_task_system.builtins import builtins
from django_common_task_system import get_schedule_model, get_schedule_serializer
from django_common_task_system.models import AbstractSchedule
from django_common_task_system.utils.logger import add_file_handler
from django_common_task_system.cache_service import cache_agent
from .config import ScheduleConfig
from threading import Thread, Event
from datetime import datetime
import time
import logging
import os


logger = logging.getLogger('schedule-thread')


Schedule: AbstractSchedule = get_schedule_model()
ScheduleSerializer = get_schedule_serializer()


class ScheduleRunner:
    schedule_event = Event()
    last_schedule_time = None
    scheduled_count = 0
    log_file = os.path.join(os.getcwd(), 'logs', 'schedule-thread.log')

    @property
    def runner_id(self) -> int:
        raise NotImplementedError

    def produce(self):
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
        self.last_schedule_time = now
        for queue_code, put_size in schedule_result.items():
            logger.info('schedule %s schedules to %s' % (put_size, queue_code))
        self.scheduled_count += count
        # 设置schedule-thread:pid的过期时间为5秒, 5秒后如果没有更新, 则认为该进程已经停止, 此set相当于心跳包
        cache_agent.set('schedule-thread:pid', self.runner_id, expire=5)
        # 设置schedule-thread的状态, 用于监控, 不用以下设置为心跳, 是因为想保留上次的状态
        cache_agent.mset(last_schedule_time=self.last_schedule_time.strftime('%Y-%m-%d %H:%M:%S'),
                         scheduled_count=self.scheduled_count, scope='schedule-thread')

    def run(self) -> None:
        add_file_handler(logger, self.log_file)
        # 等待系统初始化完成, 5秒后自动开始
        self.schedule_event.wait(timeout=5)
        self.schedule_event.set()
        SCHEDULE_INTERVAL = getattr(settings, 'SCHEDULE_INTERVAL', 1)
        is_set = self.schedule_event.is_set
        while is_set():
            try:
                self.produce()
            except Exception as e:
                logger.exception(e)
            print("scheduled_count: %s" % self.scheduled_count)
            time.sleep(SCHEDULE_INTERVAL)


class ScheduleThread(ScheduleRunner, Thread):
    def __init__(self):
        super().__init__(daemon=True)

    @property
    def runner_id(self) -> int:
        return self.ident