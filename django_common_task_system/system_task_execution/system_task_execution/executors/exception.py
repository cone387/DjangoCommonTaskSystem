from django.urls import reverse
import requests
from .base import BaseExecutor
from django.db import connection
from django_common_task_system.system_task.models import SystemScheduleLog, SystemSchedule, builtins
from django_common_task_system.models import TaskSchedule, TaskScheduleLog
from .. import settings

_columns = None


def get_schedule_table_columns(table):
    global _columns
    if not _columns:
        cmd = '''select GROUP_CONCAT(column_name SEPARATOR ',') from information_schema.`COLUMNS` 
        where column_name <> 'next_schedule_time' 
        and table_name = '%s' GROUP BY table_name''' % table
        with connection.cursor() as cursor:
            cursor.execute(cmd)
            _columns = cursor.fetchone()[0].split(',')
    return _columns


class SystemExceptionExecutor(BaseExecutor):
    name = builtins.tasks.system_exception_handling.name
    schedule_model = SystemSchedule
    schedule_log_model = SystemScheduleLog
    handle_url = 'system_schedule_queue_put'

    def execute(self):
        max_retry_times = self.schedule.task.config.get('max_retry_times', 5)
        columns = get_schedule_table_columns(table=self.schedule_model._meta.db_table)
        command = '''
            select %s, b.schedule_time as next_schedule_time from %s a join (
            select schedule_id, schedule_time, count(*) as times, status from %s where create_time > CURDATE() 
            GROUP BY schedule_id, schedule_time order by schedule_id, schedule_time
            ) b on a.id = b.schedule_id where times < %s limit 1000
        ''' % (',a.'.join(columns), self.schedule_model._meta.db_table,
               self.schedule_log_model._meta.db_table, max_retry_times)
        schedules = self.schedule_model.objects.raw(command)
        path = reverse(self.handle_url, args=(self.schedule.id,))
        url = settings.HOST + path
        result = {}
        for schedule in schedules:
            try:
                res = requests.get(url)
                result[schedule.id] = res.status_code
            except Exception as e:
                result[schedule.id] = str(e)
        return result


class ScheduleExceptionExecutor(SystemExceptionExecutor):
    name = builtins.tasks.task_exception_handling.name
    schedule_model = TaskSchedule
    schedule_log_model = TaskScheduleLog
    handle_url = 'task_schedule_put'
