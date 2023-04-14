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
from django_common_task_system.system_task.models import SystemSchedule, SystemTask, builtins
from django_common_task_system.models import TaskScheduleCallback
from django_common_task_system.choices import TaskScheduleStatus

system_task_queue = Queue()
logger = settings.logger


def query_system_schedule():

    now = datetime.now()
    queryset = SystemSchedule.objects.filter(next_schedule_time__lte=now, status=TaskScheduleStatus.OPENING.value)
    for schedule in queryset:
        system_task_queue.put(copy.deepcopy(schedule))
        schedule.generate_next_schedule()
    return queryset


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
        result['next_schedule_time'] = datetime.strptime(result.pop('schedule_time'), '%Y-%m-%d %H:%M:%S')
        return SystemSchedule(
            task=SystemTask(**task),
            callback=callback,
            **result
        )
        # system_task_queue.put(schedule)


def get_system_schedule():
    while True:
        schedule = request_system_schedule()
        if schedule:
            return schedule
        time.sleep(1)
    # try:
    #     return system_task_queue.get(timeout=2)
    # except Empty:
    #     logger.debug('\r[%s]%s' % (time.strftime('%Y-%m-%d %H:%M:%S'), 'waiting for system schedule...'))
    #     query_system_schedule()
    #     if system_task_queue.empty():
    #         request_system_schedule()
    # return get_system_schedule()


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
