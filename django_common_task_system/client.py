from logging.handlers import RotatingFileHandler
from multiprocessing import Process, set_start_method
from django_common_task_system.choices import TaskClientStatus
from docker.errors import APIError
from typing import Union
from threading import Lock
import os
import subprocess
import logging
import locale
import docker


SYS_ENCODING = locale.getpreferredencoding()

_current_process: Union[Process, None] = None
_current_process_lock = Lock()


def current_process() -> Union[Process, None]:
    return _current_process


def run_in_subprocess(cmd):
    logs = []
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if out:
        logs.append(out.decode(SYS_ENCODING))
    if err:
        logs.append(err.decode(SYS_ENCODING))
    return not err, logs


class SimpleTaskClient:

    def __init__(self, client_id: int, container_image: str, container_name: str, settings_module: dict,
                 run_in_container: bool = True, env=None, container_status=TaskClientStatus.SUCCEED):
        self.client_id = client_id
        self.container_image = container_image
        self.container_name = container_name
        self.settings_module = settings_module
        self.run_in_container = run_in_container
        self.env = env
        self.container = None
        self.container_status = container_status


def start_in_container(client):
    # pull image
    docker_client = docker.from_env()
    client.startup_status = TaskClientStatus.PULLING
    command = "common-task-system-client --subscription-url=%s" % client.subscription_url
    try:
        container = docker_client.containers.create(
            client.container_image, command=command,
            name=client.container_name, detach=True)
    except docker.errors.ImageNotFound:
        image, tag = client.container_image.split(':') if ':' in client.container_image else (
            client.container_image, None)
        for _ in range(3):
            try:
                docker_client.images.pull(image, tag=tag)
                break
            except APIError:
                pass
        else:
            raise RuntimeError('pull image failed: %s' % client.container_image)
        container = docker_client.containers.create(client.container_image,
                                                    command=command,
                                                    name=client.container_name, detach=True)
    client.container_id = container.short_id
    client.container = container
    container.start()
    container = docker_client.containers.get(container.short_id)
    client.container_status = container.status.capitalize()


def start_in_process(client):
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
    client.startup_status = TaskClientStatus.SUCCEED
    if not p.is_alive():
        raise RuntimeError('client process start failed, process is not alive')


def start_client(client):

    client.startup_status = TaskClientStatus.INIT
    try:
        if client.run_in_container:
            start_in_container(client)
        else:
            start_in_process(client)
        client.startup_status = TaskClientStatus.SUCCEED
    except Exception as e:
        client.startup_status = TaskClientStatus.FAILED
        client.startup_log = str(e)


def start_system_process() -> str:
    global _current_process, _current_process_lock
    error = ''
    if _current_process is not None:
        error = 'process already started'
    else:
        lock = _current_process_lock.acquire(blocking=False)
        if not lock:
            error = 'another process is starting'
        else:
            from django_common_task_system.builtins import builtins
            from django_common_task_system.system_task_execution import main
            set_start_method('spawn', True)
            try:
                _current_process = Process(target=main.start_system_client, args=(builtins.schedule_queues.system.queue, ),
                                           daemon=True)
                _current_process.start()
            except Exception as e:
                error = str(e)
            finally:
                _current_process_lock.release()
    return error


def stop_system_process():
    global _current_process
    error = ''
    if _current_process is None:
        error = 'process not started'
    else:
        lock = _current_process_lock.acquire(blocking=False)
        if not lock:
            error = 'another process is processing'
        else:
            try:
                _current_process.kill()
                _current_process = None
            except Exception as e:
                error = str(e)
            finally:
                _current_process_lock.release()
    return error


def restart_system_process():
    error = stop_system_process()
    if not error:
        error = start_system_process()
    return error
