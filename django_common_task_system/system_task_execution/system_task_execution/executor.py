import os
import time
import copy
import requests
from queue import Queue, Empty
from datetime import datetime
from django.urls import reverse
from .executors import Executors
from . import settings
from urllib.parse import urljoin
from django_common_task_system.system_task.models import SystemSchedule, SystemTask
from django_common_task_system.models import TaskScheduleCallback


system_task_queue = Queue()
logger = settings.logger


def request_system_schedule():

    url = urljoin(settings.HOST, reverse('system_schedule_get', args=('opening', )))
    response = requests.get(url)
    if response.status_code == 200:
        result = response.json()
        callback = result.pop('callback')
        if callback:
            callback = TaskScheduleCallback(**callback)
        task = result.pop('task')
        category = task.pop('category')
        tags = task.pop('tags', None)
        user = result.pop('user', None)
        queue = result.pop('queue', None)
        parent = task.pop('parent', None)
        if parent:
            parent.pop('category')
            parent.pop('tags')
            parent = SystemTask(**parent)
        result['next_schedule_time'] = datetime.strptime(result.pop('schedule_time'), '%Y-%m-%d %H:%M:%S')
        schedule = SystemSchedule(
            task=SystemTask(parent=parent, **task),
            callback=callback,
            **result
        )
        schedule.queue = queue
        return schedule
        # system_task_queue.put(schedule)


def get_system_schedule():
    while True:
        schedule = request_system_schedule()
        if schedule:
            return schedule
        time.sleep(1)


def get_schedule_executor(schedule):
    try:
        if not schedule.task.parent:
            raise KeyError
        cls = Executors[schedule.task.parent.name]
    except KeyError:
        try:
            cls = Executors[schedule.task.name]
        except KeyError:
            raise RuntimeError('executor not found for task name: %s' % schedule.task.name)
    return cls(schedule)


def run():
    schedule = get_system_schedule()
    logger.info('get system schedule: %s', schedule)
    executor = get_schedule_executor(schedule)
    log, err = executor.start()
    if not err:
        logger.info('system schedule execute success: %s', log.result)


def start_client(**kwargs):
    logger.info('system executor start')
    for k, v in os.environ.items():
        logger.info('Env: %s -> %s' % (k, v))
    while True:
        try:
            run()
        except Exception as e:
            logger.exception(e)
