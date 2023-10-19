import threading
import time
from django_common_task_system.system_task_execution.system_task_execution.consumer import Consumer
from django_common_task_system.builtins import builtins


class ScheduleConsumerThread(Consumer, threading.Thread):
    def __init__(self):
        super(ScheduleConsumerThread, self).__init__(queue=builtins.schedule_queues.system.queue)
        threading.Thread.__init__(self, daemon=True)

    @property
    def program_id(self) -> int:
        return self.ident

    def stop(self, destroy=False) -> str:
        while self.is_alive():
            time.sleep(0.5)
        return ''
