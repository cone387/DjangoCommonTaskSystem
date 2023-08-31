from logging.handlers import RotatingFileHandler
from multiprocessing import Process, set_start_method
from django_common_task_system.choices import TaskClientStatus, ClientEngineType
from django_common_task_system.schedule.backend import ScheduleThread
from django_common_task_system.models import TaskClient, DockerEngine
from docker.errors import APIError
from django.conf import settings
from typing import Union
from threading import Lock, Timer, Thread
from docker.models.containers import Container
from django_common_task_system.system_task_execution.main import SystemScheduleProcess
import os
import traceback
import subprocess
import logging
import locale
import docker
import math


SYS_ENCODING = locale.getpreferredencoding()

_current_process: Union[Process, None] = None
_current_process_lock = Lock()

_schedule_thread: Union[ScheduleThread, None] = None
_schedule_thread_lock = Lock()


def current_process():
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


def start_system_process() -> str:
    global _current_process, _current_process_lock
    error = ''
    if _current_process is not None:
        error = 'process already started'
    else:
        if not _current_process_lock.acquire(blocking=False):
            error = 'another process is starting'
        else:
            from django_common_task_system.builtins import builtins
            set_start_method('spawn', True)
            try:
                _current_process = SystemScheduleProcess(
                    builtins.schedule_queues.system.queue,
                    log_file=getattr(settings, 'SYSTEM_PROCESS_LOG_FILE'))
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
        if not _current_process_lock.acquire(blocking=False):
            error = 'another process is processing'
        else:
            from django_common_task_system.builtins import builtins
            try:
                _current_process.kill()
                _current_process = None
                _rlock = getattr(builtins.schedule_queues.system.queue, '_rlock', None)
                if _rlock is not None:
                    # release _rlock, otherwise the new process will be blocked
                    try:
                        _rlock.release()
                    except RuntimeError:
                        pass
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


class PagedLog:
    def __init__(self, log_file, page_size=10 * 1024):
        with open(log_file, 'r', encoding='utf-8') as f:
            size = f.seek(0, os.SEEK_END)
            self.page_num = math.ceil(size / page_size)
        self.log_file = log_file
        self.page_size = page_size
        self.page_range = range(1, self.page_num + 1)
        self.current = 1
        self.max_display_page = 10

    @property
    def right_offset(self):
        return max(self.current + self.max_display_page // 2, self.max_display_page)

    @property
    def left_offset(self):
        offset = self.current - self.max_display_page // 2
        if offset < 0:
            offset = 0
        return offset

    @property
    def max_offset(self):
        return self.page_num - self.max_display_page

    @property
    def real_page_size(self):
        return self.page_size // 1024

    def read_page(self, page=0):
        if page == 0:
            page = self.page_num
        if self.page_num == 0:
            return "log file is empty"
        if page > self.page_num or page < 1:
            return f"page({page}) out of range"
        self.current = page
        with open(self.log_file, 'r', encoding='utf-8') as f:
            f.seek((page - 1) * self.page_size, os.SEEK_SET)
            log = f.read(self.page_size)
        return log


def read_system_process_log(page_size=10 * 1024) -> Union[PagedLog, None]:
    log_file = getattr(settings, 'SYSTEM_PROCESS_LOG_FILE', None)
    if not os.path.isfile(log_file):
        return None
    return PagedLog(log_file, page_size)


def current_schedule_thread():
    return _schedule_thread


def start_schedule_thread():
    global _schedule_thread
    if _schedule_thread is not None:
        error = "another schedule thread is running"
    else:
        if _schedule_thread_lock.acquire(blocking=False):
            _schedule_thread = ScheduleThread()
            _schedule_thread.start()
            _schedule_thread_lock.release()
            error = ''
        else:
            error = 'another action to thread is processing'
    return error


def listen_schedule_thread():
    global _schedule_thread
    if _schedule_thread is not None:
        if _schedule_thread.is_alive():
            Timer(1, listen_schedule_thread).start()
        else:
            _schedule_thread_lock.release()
            _schedule_thread = None


def stop_schedule_thread() -> str:
    global _schedule_thread
    if _schedule_thread is None:
        error = 'schedule thread not started'
    else:
        if not _schedule_thread_lock.acquire(blocking=False):
            error = 'another action to thread is processing'
        else:
            if _schedule_thread.schedule_event.is_set():
                _schedule_thread.schedule_event.clear()
            listen_schedule_thread()
            if _schedule_thread.is_alive():
                error = 'schedule thread is stopping'
            else:
                error = ''
    return error


def read_schedule_thread_log(page_size=10 * 1024) -> Union[PagedLog, None]:
    if not os.path.isfile(ScheduleThread.log_file):
        return None
    return PagedLog(ScheduleThread.log_file, page_size)
