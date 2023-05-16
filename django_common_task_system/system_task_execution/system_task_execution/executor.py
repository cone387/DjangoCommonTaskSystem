import os
import time
import traceback
import socket
import requests
from queue import Queue
from datetime import datetime
from django.urls import reverse
from .executors import Executors
from . import settings
from urllib.parse import urljoin
from .utils import to_model
from django_common_task_system.system_task.models import SystemSchedule, SystemExceptionReport
from django_common_task_system.system_task.builtins import builtins


IP = socket.gethostbyname(socket.gethostname())
system_task_queue = Queue()
logger = settings.logger


def request_system_schedule(url):
    response = requests.get(url)
    if response.status_code == 200:
        result = response.json()
        result['next_schedule_time'] = datetime.strptime(result.pop('schedule_time'), '%Y-%m-%d %H:%M:%S')
        schedule = to_model(result, SystemSchedule)
        schedule.queue = result.pop('queue', None)
        schedule.generator = result.pop('generator', None)
        return schedule


def get_system_schedule(url):
    while True:
        schedule = request_system_schedule(url)
        if schedule:
            return schedule
        time.sleep(1)


def get_schedule_executor(schedule):
    try:
        cls = Executors[schedule.task.name]
    except KeyError:
        try:
            cls = Executors[schedule.task.parent.name]
        except KeyError:
            raise RuntimeError('executor not found for task name: %s' % schedule.task.name)
    return cls(schedule)


def run(schedule):
    executor = get_schedule_executor(schedule)
    log, err = executor.start()
    if not err:
        logger.info('system schedule execute success: %s', log.result)


def start_client(queue=None, **kwargs):
    logger.info('system executor start')
    for k, v in os.environ.items():
        logger.info('Env: %s -> %s' % (k, v))
    consumer_url = urljoin(settings.HOST, reverse('system_schedule_get', args=(queue or builtins.queues.opening.code,)))
    while True:
        try:
            schedule = get_system_schedule(consumer_url)
            logger.info('get system schedule: %s', schedule)
            run(schedule)
        except Exception as e:
            logger.exception(e)
            try:
                SystemExceptionReport.objects.create(
                    ip=IP,
                    content=traceback.format_exc(),
                )
            except Exception as e:
                logger.exception(e)
