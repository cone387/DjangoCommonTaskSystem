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
    handle_url = 'system_schedule_put'

    def execute(self):
        max_retry_times = self.schedule.task.config.get('max_retry_times', 5)
        max_fetch_num = self.schedule.task.config.get('max_fetch_num', 1000)
        # columns = get_schedule_table_columns(table=self.schedule_model._meta.db_table)
        command = '''
            select * from (
            select queue, schedule_id, schedule_time, count(*) as times from %s where create_time > CURDATE() 
            and status != 'S' 
            GROUP BY queue, schedule_id, schedule_time order by schedule_id, schedule_time
            ) where times < %s limit %s
        ''' % (self.schedule_log_model._meta.db_table, max_retry_times, max_fetch_num)
        with connection.cursor() as cursor:
            cursor.execute(command)
            rows = cursor.fetchall()
        if rows:
            path = reverse(self.handle_url)
            ids, queues, times = [], [], []
            for q, i, t, _ in rows:
                ids.append(str(i))
                queues.append(q)
                times.append(t.strftime('%Y-%m-%d %H:%M:%S'))
            url = settings.HOST + path
            return requests.get(url, params={
                'i': ','.join(ids),
                'q': ','.join(queues),
                't': ','.join(times)
            }).json()
        return "no schedule need to retry"


class ScheduleExceptionExecutor(SystemExceptionExecutor):
    name = builtins.tasks.task_exception_handling.name
    schedule_model = TaskSchedule
    schedule_log_model = TaskScheduleLog
    handle_url = 'task_schedule_put'
