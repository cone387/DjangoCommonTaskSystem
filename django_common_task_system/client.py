from logging.handlers import RotatingFileHandler
from multiprocessing import Process, set_start_method
from django_common_task_system.choices import TaskClientStatus, ClientEngineType
from django_common_task_system.models import TaskClient, DockerEngine
from docker.errors import APIError
from threading import Thread
from docker.models.containers import Container
import os
import traceback
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


def run_in_container(client):
    # pull image
    docker_client = docker.from_env()
    client.startup_status = TaskClientStatus.PULLING
    engine: DockerEngine = client.engine
    settings_file = '/mnt/task-system-client-settings.py'
    command = f'common-task-system-client --subscription-url="{client.subscription_url}" --settings="{settings_file}"'
    try:
        container = docker_client.containers.create(
            engine.image, command=command, name=engine.container_name,
            volumes=[f"{client.settings_file}:{settings_file}"],
            detach=True
        )
    except docker.errors.ImageNotFound:
        image, tag = engine.image.split(':') if ':' in engine.image else (
            engine.image, None)
        for _ in range(3):
            try:
                docker_client.images.pull(image, tag=tag)
                break
            except APIError:
                pass
        else:
            raise RuntimeError('pull image failed: %s' % engine.image)
        container = docker_client.containers.create(engine.image,
                                                    command=command,
                                                    name=engine.container_name, detach=True)
    container.start()
    container = docker_client.containers.get(container.short_id)
    return container


def run_in_process(client):
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
    client.startup_status = TaskClientStatus.RUNNING
    if not p.is_alive():
        raise RuntimeError('client process start failed, process is not alive')
    return p


class ClientRunner:
    def __init__(self, client: TaskClient):
        if client.runner is None:
            client.runner = self
            self.runner = None
        else:
            self.runner = client.runner.runner
        self.client = client

    @property
    def attrs(self):
        runner = self.runner
        if isinstance(runner, Container):
            return {
                'image': runner.image.tags[0],
                'name': runner.name,
            }
        elif isinstance(runner, Process):
            return {
                'process_id': runner.pid,
            }
        else:
            return {}

    @property
    def status(self):
        runner = self.runner
        if isinstance(runner, Container):
            return runner.status.capitalize()
        elif isinstance(runner, Process):
            return TaskClientStatus.RUNNING if runner.is_alive() else TaskClientStatus.FAILED
        else:
            return None

    @property
    def id(self):
        runner = self.runner
        if isinstance(runner, Container):
            return runner.short_id
        elif isinstance(runner, Process):
            return runner.pid
        else:
            return None

    def stop(self):
        if isinstance(self.runner, Container):
            self.runner.stop()
            self.runner.remove()
        elif isinstance(self.runner, Process):
            self.runner.kill()

    def read_log(self, page=1, page_size=10):
        if isinstance(self.runner, Container):
            return self.runner.logs(tail=1000)
        elif isinstance(self.runner, Process):
            return ''

    def start(self):
        client = self.client
        try:
            if client.engine_type == ClientEngineType.DOCKER:
                self.runner = run_in_container(client)
            else:
                self.runner = run_in_process(client)
            client.startup_status = TaskClientStatus.RUNNING
        except Exception:
            client.startup_status = TaskClientStatus.FAILED
            client.startup_log = traceback.format_exc()


def start_client(client: TaskClient):
    client.startup_status = TaskClientStatus.INIT
    runner = ClientRunner(client)
    thread = Thread(target=runner.start)
    thread.start()
