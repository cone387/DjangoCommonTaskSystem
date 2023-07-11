from logging.handlers import RotatingFileHandler
from multiprocessing import Process, set_start_method
from django_common_task_system.generic.models import TaskClient
from django_common_task_system.generic.choices import TaskClientStatus
from docker.errors import APIError
import os
import subprocess
import logging
import locale
import docker


SYS_ENCODING = locale.getpreferredencoding()


def run_in_subprocess(cmd):
    logs = []
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if out:
        logs.append(out.decode(SYS_ENCODING))
    if err:
        logs.append(err.decode(SYS_ENCODING))
    return not err, logs


def start_in_container(client: TaskClient):
    # pull image
    docker_client = docker.from_env()
    image, tag = client.container_image.split(':') if ':' in client.container_image else (client.container_image, None)
    client.status = TaskClientStatus.PULLING
    for _ in range(3):
        try:
            container_image = docker_client.images.pull(image, tag=tag)
            break
        except APIError:
            pass
    else:
        raise RuntimeError('pull image failed: %s' % client.container_image)
    container = docker_client.containers.create(container_image, name=client.container_name, detach=True)
    client.container_id = container.short_id
    client.container = container


def start_in_process(client: TaskClient):
    set_start_method('spawn', True)
    os.environ['TASK_CLIENT_SETTINGS_MODULE'] = client.settings_file.replace(
        os.getcwd(), '').replace(os.sep, '.').strip('.py')
    try:
        from task_system_client.main import start_task_system
    except ImportError:
        os.system('pip install common-task-system-client')
        try:
            from task_system_client.main import start_task_system
        except ImportError:
            raise RuntimeError('common-task-system-client install failed')
    from task_system_client.settings import logger
    logger.handlers.clear()
    if os.path.isfile(client.log_file):
        os.remove(client.log_file)
    handler = RotatingFileHandler(client.log_file, maxBytes=1024 * 1024 * 10, encoding='utf-8', backupCount=5)
    formatter = logging.Formatter('[%(asctime)s][%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    p = Process(target=start_task_system, daemon=True)
    p.start()
    client.client_id = p.pid
    if not p.is_alive():
        raise RuntimeError('client process start failed, process is not alive')


def start_client(client: TaskClient):
    try:
        if client.run_in_container:
            start_in_container(client)
        else:
            start_in_process(client)
        client.status = TaskClientStatus.RUNNING
    except Exception as e:
        client.status = TaskClientStatus.FAILED
        client.startup = str(e)
