import os
from multiprocessing import Process
from django_common_task_system.system_task_execution.system_task_execution.consumer import Consumer
from django_common_task_system.builtins import builtins


class ScheduleConsumerProcess(Consumer, Process):

    def __init__(self):
        super(ScheduleConsumerProcess, self).__init__(queue=builtins.schedule_queues.system.queue)
        Process.__init__(self, daemon=True)

    def run(self):
        import django
        os.environ['RUN_CLIENT'] = 'true'
        assert os.environ.get('DJANGO_SETTINGS_MODULE'), 'django settings module not found'
        django.setup()
        super(ScheduleConsumerProcess, self).run()

    def stop(self, destroy=False):
        super(ScheduleConsumerProcess, self).stop(destroy=destroy)
        self.kill()
