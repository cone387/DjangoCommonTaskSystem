from threading import Thread
from django_common_task_system.system_task_execution.system_task_execution.consumer import Consumer
from django_common_task_system.builtins import builtins


class ScheduleConsumerThread(Consumer, Thread):

    def __init__(self):
        super(ScheduleConsumerThread, self).__init__(queue=builtins.schedule_queues.system.queue)
        Thread.__init__(self, daemon=True)

    @property
    def id(self):
        return self.ident


consume_thread = ScheduleConsumerThread()
