from django.conf import settings
from .choices import ScheduleStatus
from .schedule_config import ScheduleConfig
from threading import Thread, Event
from datetime import datetime
import time
import traceback
from .builtins import builtins


class TaskScheduleThread(Thread):

    def __init__(self, schedule_model, schedule_serializer):
        self.schedule_model = schedule_model
        self.producers = builtins.schedule_producers
        self.queues = builtins.schedule_queues
        self.schedule_serializer = schedule_serializer
        self._event = Event()
        super().__init__(daemon=True)

    def produce(self):
        now = datetime.now()
        qsize = getattr(settings, 'SCHEDULE_QUEUE_MAX_SIZE', 1000)
        max_queue_size = qsize * 2
        for producer in self.producers.values():
            queue_instance = self.queues[producer.queue.code]
            queue = queue_instance.queue
            # 队列长度大于1000时不再生产, 防止内存溢出
            if queue.qsize() >= qsize:
                continue
            queryset = self.schedule_model.objects.filter(**producer.filters)
            if producer.lte_now:
                queryset = queryset.filter(next_schedule_time__lte=now)
            for schedule in queryset:
                try:
                    # 限制队列长度, 防止内存溢出
                    while queue.qsize() < max_queue_size and schedule.next_schedule_time <= now:
                        schedule.queue = queue_instance.code
                        data = self.schedule_serializer(schedule).data
                        queue.put(data)
                        schedule.next_schedule_time = ScheduleConfig(config=schedule.config
                                                                     ).get_next_time(schedule.next_schedule_time)
                    schedule.save(update_fields=('next_schedule_time', ))
                except Exception as e:
                    schedule.status = ScheduleStatus.ERROR.value
                    schedule.save(update_fields=('status',))
                    traceback.print_exc()

    def run(self) -> None:
        # 等待系统初始化完成, 5秒后自动开始
        self._event.wait(timeout=5)
        SCHEDULE_INTERVAL = getattr(settings, 'SCHEDULE_INTERVAL', 1)
        while True:
            try:
                self.produce()
            except Exception as err:
                traceback.print_exc()
            time.sleep(SCHEDULE_INTERVAL)

