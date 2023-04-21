import os
import argparse
import sys
import logging
from logging.handlers import RotatingFileHandler


def start_system_client(log_file=None, **kwargs):
    os.environ['RUN_CLIENT'] = 'true'
    parser = argparse.ArgumentParser()
    parser.add_argument('--system-path', type=str, required=False)
    parser.add_argument('--system-setting', type=str, required=False)
    shell_args = parser.parse_known_args()[0]
    if shell_args.system_path:
        assert os.path.exists(shell_args.system_path), 'system path not found'
        sys.path.append(shell_args.system_path)
    env = shell_args.system_setting or os.environ.get('DJANGO_SETTINGS_MODULE')
    assert env, 'django settings module not found'
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', env)
    import django
    django.setup()

    if log_file:
        from .system_task_execution import settings
        logger = settings.logger
        logger.handlers.clear()
        if not os.path.exists(os.path.dirname(log_file)):
            os.makedirs(os.path.dirname(log_file))
        if os.path.isfile(log_file):
            os.remove(log_file)
        handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024 * 10, encoding='utf-8', backupCount=5)
        formatter = logging.Formatter('[%(asctime)s][%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    from django_common_task_system.system_task_execution.system_task_execution.executor import start_client
    start_client(**kwargs)


if __name__ == '__main__':
    start_system_client()
