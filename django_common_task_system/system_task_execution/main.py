import os
import logging
from logging.handlers import RotatingFileHandler


logger = logging.getLogger(__name__)
console_handler = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)s][%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.setLevel(logging.INFO)


def start_system_client(queue):
    os.environ['RUN_CLIENT'] = 'true'
    assert os.environ.get('DJANGO_SETTINGS_MODULE'), 'django settings module not found'
    import django
    django.setup()

    from django.conf import settings
    if not hasattr(settings, 'SYSTEM_PROCESS_LOG_FILE'):
        setattr(settings, 'SYSTEM_PROCESS_LOG_FILE', 'system-task-execution.log')
    log_file = settings.SYSTEM_PROCESS_LOG_FILE

    if log_file:
        log_file = os.path.join(os.getcwd(), 'logs', log_file)
        logger.handlers.clear()
        if not os.path.exists(os.path.dirname(log_file)):
            os.makedirs(os.path.dirname(log_file))
        if os.path.isfile(log_file):
            os.remove(log_file)
        handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024 * 10, encoding='utf-8', backupCount=5)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    from django_common_task_system.system_task_execution.system_task_execution.executor import start_client
    start_client(queue)
