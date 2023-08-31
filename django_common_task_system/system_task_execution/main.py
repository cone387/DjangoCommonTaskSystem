import logging
import os
from multiprocessing import Process, Value


def start_system_client(queue, success_count, failed_count, last_process_time, log_file=None):
    os.environ['RUN_CLIENT'] = 'true'
    assert os.environ.get('DJANGO_SETTINGS_MODULE'), 'django settings module not found'
    import django
    from django_common_task_system.utils.logger import add_file_handler
    django.setup()

    add_file_handler(logging.getLogger('client'), log_file=log_file)
    from django_common_task_system.system_task_execution.system_task_execution.executor import start_client
    start_client(queue, success_count, failed_count, last_process_time)


class SystemScheduleProcess(Process):
    success_count = Value('i', 0)
    failed_count = Value('i', 0)
    last_process_time = Value('d', 0)

    def __init__(self, queue, log_file=None):
        super(SystemScheduleProcess, self).__init__(
            target=start_system_client,
            args=(queue, self.success_count, self.failed_count, self.last_process_time, log_file),
            daemon=True)
