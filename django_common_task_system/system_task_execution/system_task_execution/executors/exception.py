from django.urls import reverse
import requests
from .base import BaseExecutor
from django.db import connection
from django_common_task_system.system_task.models import SystemScheduleLog, SystemSchedule, builtins
from django_common_task_system import get_task_schedule_model, get_schedule_log_model
from django_common_task_system.models import ScheduleConfig
from .. import settings

_columns = None

TaskScheduleLog = get_schedule_log_model()
TaskSchedule = get_task_schedule_model()


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
    schedule_id = builtins.schedules.system_exception_handling.id
    schedule_model = SystemSchedule
    schedule_log_model = SystemScheduleLog
    handle_url = 'system_schedule_put'

    def execute(self):
        max_retry_times = self.schedule.task.config.get('max_retry_times', 5)
        max_fetch_num = self.schedule.task.config.get('max_fetch_num', 1000)
        # columns = get_schedule_table_columns(table=self.schedule_model._meta.db_table)
        next_schedule_time = ScheduleConfig(config=self.schedule.config).get_next_time(
            self.schedule.next_schedule_time)
        last_schedule_time = self.schedule.next_schedule_time - (next_schedule_time - self.schedule.next_schedule_time)
        command = '''
            select * from (
            select queue, schedule_id, schedule_time, count(*) as times, max(create_time) as lastest_time 
            from %s where create_time > CURDATE() and status != 'S' 
            GROUP BY queue, schedule_id, schedule_time order by queue, schedule_id, schedule_time
            ) a where a.times < %s and a.lastest_time > '%s' limit %s
        ''' % (self.schedule_log_model._meta.db_table, max_retry_times, last_schedule_time, max_fetch_num,)
        with connection.cursor() as cursor:
            cursor.execute(command)
            rows = list(cursor.fetchall())
        batch_num = 1000
        i = 0
        batch = rows[:batch_num]
        result = {}
        error = None
        while batch:
            path = reverse(self.handle_url)
            ids, queues, times = [], [], []
            for q, i, t, *_ in batch:
                if i == self.schedule_id:
                    continue
                ids.append(str(i))
                queues.append(q)
                times.append(t.strftime('%Y-%m-%d %H:%M:%S'))
            url = settings.HOST + path
            batch_result = requests.get(url, params={
                'i': ','.join(ids),
                'q': ','.join(queues),
                't': ','.join(times)
            }).json()
            result[i] = batch_result
            if 'error' in batch_result:
                error = batch_result['error']
            i += 1
            batch = rows[i * batch_num: (i + 1) * batch_num]
        if error:
            raise Exception(error)
        return result


class ScheduleExceptionExecutor(SystemExceptionExecutor):
    name = builtins.tasks.task_exception_handling.name
    schedule_model = TaskSchedule
    schedule_id = builtins.schedules.task_exception_handling.id
    schedule_log_model = TaskScheduleLog
    handle_url = 'task_schedule_put'
