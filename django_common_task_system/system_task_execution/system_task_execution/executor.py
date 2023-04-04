
import time
import sys
import copy
from queue import Queue, Empty
from datetime import datetime
from .executors import Executors
from .settings import logger
from django_common_task_system.system_task.choices import SystemTaskType

system_task_queue = Queue()


def query_system_schedule():
    from django_common_task_system.choices import TaskScheduleStatus
    from django_common_task_system.system_task.models import SystemSchedule
    now = datetime.now()
    queryset = SystemSchedule.objects.filter(next_schedule_time__lte=now, status=TaskScheduleStatus.OPENING.value)
    for schedule in queryset:
        system_task_queue.put(copy.deepcopy(schedule))
        schedule.generate_next_schedule()
    return queryset


def get_system_schedule():
    try:
        return system_task_queue.get(timeout=2)
    except Empty:
        sys.stdout.write('\r[%s]%s' % (time.strftime('%Y-%m-%d %H:%M:%S'), 'waiting for system schedule...'))
        sys.stdout.flush()
        query_system_schedule()
    return get_system_schedule()


def get_schedule_executor(schedule):
    if schedule.task.task_type == SystemTaskType.CUSTOM:
        try:
            cls = Executors[schedule.task.name]
        except KeyError:
            raise RuntimeError('executor not found for task type: %s' % schedule.task.name)
    else:
        try:
            cls = Executors[schedule.task.task_type]
        except KeyError:
            raise RuntimeError('executor not found for task type: %s' % schedule.task.task_type)
    return cls(schedule)


class Runner(object):

    def __init__(self, sys_path, sys_settings=None):
        self.sys_path = sys_path
        self.sys_settings = sys_settings

    def run(self):
        schedule = get_system_schedule()
        logger.info('get system schedule: %s', schedule)
        executor = get_schedule_executor(schedule)
        log, err = executor.start()
        if not err:
            logger.info('system schedule execute success: %s', log.result)

    def start(self):
        run = self.run
        logger.info('system executor start')
        while True:
            try:
                run()
            except Exception as e:
                logger.exception(e)

