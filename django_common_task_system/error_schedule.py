import os
import time

from django.db.models import Count
from django.utils.module_loading import import_string
from django.conf import settings
from datetime import datetime


error_handler_process = None


class ScheduleErrorHandler:

    def run(self):
        import django
        django.setup()

        from django.db.models import Q, F
        from django_common_task_system import get_task_schedule_model, get_schedule_log_model
        from django.db import connection
        from django_common_task_system.serializers import QueueScheduleSerializer
        from django_common_task_system.choices import TaskScheduleStatus
        TaskSchedule = get_task_schedule_model()
        TaskScheduleLog = get_schedule_log_model()
        while True:
            now = datetime.now()
            with connection.cursor() as cursor:
                cmd = f"""
                    select a.*, b.schedule_time, b.times from {TaskSchedule._meta.db_table} a join (
                select schedule_id, schedule_time, count(*) as times from {TaskScheduleLog._meta.db_table}  
                where status = 'F' 
                group by schedule_id, schedule_time) b on a.id = b.schedule_id where times < 5
                """.strip()
                cursor.execute(cmd)
                result = cursor.fetchall()
            print(result)
            time.sleep(1)


def get_error_handler() -> ScheduleErrorHandler:
    if not hasattr(settings, 'SCHEDULE_ERROR_HANDLER'):
        setattr(settings, 'SCHEDULE_ERROR_HANDLER', 'django_common_task_system.error_schedule.ScheduleErrorHandler')
    if not settings.SCHEDULE_ERROR_HANDLER:
        raise ImportError('SCHEDULE_ERROR_HANDLER not set')
    return import_string(settings.SCHEDULE_ERROR_HANDLER)()


def run_error_handler():
    global error_handler_process
    if os.environ.get('RUN_MAIN', None) == 'true':
        from multiprocessing import Process
        handler = get_error_handler()
        error_handler_process = Process(target=handler.run, daemon=False)
        error_handler_process.start()
        print('ErrorHandlerProcess started, pid is', error_handler_process.pid)
    return error_handler_process


