import logging
import os


def start_system_client(queue, log_file=None):
    os.environ['RUN_CLIENT'] = 'true'
    assert os.environ.get('DJANGO_SETTINGS_MODULE'), 'django settings module not found'
    import django
    from django_common_task_system.utils.logger import add_file_handler
    django.setup()

    add_file_handler(logging.getLogger('client'), log_file=log_file)
    from django_common_task_system.system_task_execution.system_task_execution.executor import start_client
    start_client(queue)
