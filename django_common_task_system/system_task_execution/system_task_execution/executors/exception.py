from .base import BaseExecutor
from django.db import connection
from django_common_task_system.system_task.models import SystemScheduleLog, SystemSchedule


_columns = None


def get_table_columns():
    global _columns
    if not _columns:
        cmd = '''select GROUP_CONCAT(column_name SEPARATOR ',') from information_schema.`COLUMNS` 
        where column_name <> 'next_schedule_time' 
        and table_name = '%s' GROUP BY table_name''' % SystemSchedule._meta.db_table
        with connection.cursor() as cursor:
            cursor.execute(cmd)
            _columns = cursor.fetchone()[0].split(',')
    return _columns


class ExceptionExecutor(BaseExecutor):
    name = '异常处理'

    def execute(self):
        max_retry_times = self.schedule.task.config.get('max_retry_times', 5)
        columns = get_table_columns()
        command = '''
            select %s, b.schedule_time as next_schedule_time from %s a join (
            select schedule_id, schedule_time, count(*) as times, status from %s where create_time > CURDATE() 
            GROUP BY schedule_id, schedule_time order by schedule_id, schedule_time
            ) b on a.id = b.schedule_id where times < %s limit 1000
        ''' % (',a.'.join(columns), SystemSchedule._meta.db_table, SystemScheduleLog._meta.db_table, max_retry_times)
        schedules = SystemSchedule.objects.raw(command)
        SystemScheduleLog.objects.filter(
            status='F',
            schedule__in=schedules).update(status=SystemScheduleLog.Status.RETRY.value)
        for schedule in schedules:
            try:
                schedule.retry()
            except Exception as e:
                print(e)

