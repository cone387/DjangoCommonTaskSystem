from django.db import connection
from datetime import datetime
from dateutil import parser
from django.db.models import Count, Max
from django_common_task_system.choices import ExecuteStatus
from django_common_task_system import get_schedule_log_model, get_schedule_model
from .config import ScheduleConfig
import copy


def _get_schedule_start_end_time(schedule, start_time=None, end_time=None):
    schedule_config = ScheduleConfig(config=schedule.config)
    if not start_time:
        update_time = schedule.update_time
        start_time = schedule.config[schedule.config['schedule_type']].get('schedule_start_time', None)
        if start_time:
            start_time = parser.parse(start_time)
            while start_time < update_time:
                start_time = schedule_config.get_next_time(start_time)
        else:
            start_time = update_time
    end_time = end_time or datetime.now()
    if isinstance(start_time, str):
        start_time = parser.parse(start_time)
    if isinstance(end_time, str):
        start_time = parser.parse(end_time)
    return start_time, end_time


def get_schedule_times(schedule, start_time=None, end_time=None):
    schedule_times = []
    start_time, end_time = _get_schedule_start_end_time(schedule, start_time, end_time)
    schedule_config = ScheduleConfig(config=schedule.config)
    while start_time < end_time:
        start_time = schedule_config.get_next_time(start_time)
        schedule_times.append(start_time)
    return schedule_times


def get_history_schedules(schedule, start_time=None, end_time=None):
    schedules = []
    start_time, end_time = _get_schedule_start_end_time(schedule, start_time, end_time)
    schedule_config = ScheduleConfig(config=schedule.config)
    while start_time < end_time:
        start_time = schedule_config.get_next_time(start_time)
        history = copy.copy(schedule)
        history.next_schedule_time = start_time
        schedules.append(history)
    return schedules


def get_log_missing_records(schedule, start_time=None, end_time=None):
    ScheduleLogModel = get_schedule_log_model()
    missing = []
    schedule.config['base_on_now'] = False
    schedule_times = get_schedule_times(schedule, start_time=start_time, end_time=end_time)
    diffs = set()
    if len(schedule_times) < 2:
        # 处理只有一个时间的情况
        return missing
    for i in range(len(schedule_times) - 1):
        a = schedule_times[i]
        b = schedule_times[i + 1]
        diff = b - a
        seconds = int(diff.total_seconds())
        diffs.add(seconds)
    if len(diffs) != 1:
        # 处理有多个间隔的情况
        return missing
    diff = diffs.pop()
    if diff % (3600 * 24) == 0:
        dimension = 'DAY'
        interval = diff // (3600 * 24)
    elif diff % 3600 == 0:
        dimension = 'HOUR'
        interval = diff // 3600
    elif diff % 60 == 0:
        dimension = 'MINUTE'
        interval = diff // 60
    else:
        # 处理间隔不是整数的情况
        return missing
    start_time, end_time = schedule_times[0], schedule_times[-1]
    lens = len(schedule_times)
    # 这里batch=700是因为mysql.help_topic表的最大id是699，也就是700条数据
    batch = 700
    schedule_date_commands = []
    for i, x in enumerate(range(0, lens, batch)):
        b = x + batch - 1 if x + batch - 1 < lens else lens - 1
        st, et = schedule_times[x], schedule_times[b]
        schedule_date_commands.append(f"""
                                SELECT
                                date_add('{st}', INTERVAL + t{i}.help_topic_id * {interval} {dimension} ) AS date 
                            FROM
                                mysql.help_topic t{i} 
                            WHERE
                                t{i}.help_topic_id <= timestampdiff({dimension}, '{st}', '{et}') 
                            """)
    schedule_date_command = ' union all '.join(schedule_date_commands)
    command = f"""
                select a.date, b.failed from ({schedule_date_command}) a 
                left join (
                    select schedule_time, count(status = 'F' or null) as failed, count(status) as log_num 
                    from {ScheduleLogModel._meta.db_table} 
                    where 
                        schedule_id = {schedule.id} and 
                        schedule_time between '{start_time}' and '{end_time}'
                    group by schedule_time
                ) b 
                on a.date = b.schedule_time where b.failed is not null or b.log_num is null
            """
    time = schedule.config[schedule.config['schedule_type']].get('time', '03:00:00')
    with connection.cursor() as cursor:
        cursor.execute(command)
        for d, f in cursor.fetchall():
            # 根据日志查出来的遗漏日期就是实际的日期，不需要根据latest_days来计算
            if len(d) == 10:
                d = d + ' ' + time
            missing.append((parser.parse(d), f))
    return missing


def get_missing_schedules(schedule, start_time=None, end_time=None):
    missing = []
    for schedule_time in get_log_missing_records(schedule, start_time=start_time, end_time=end_time):
        o = copy.copy(schedule)
        o.next_schedule_time = schedule_time
        missing.append(o)
    return missing


def get_missing_schedules_mapping(schedules,
                                  start_time=None, end_time=None):
    result = {}
    for schedule in schedules:
        result[schedule.id] = get_missing_schedules(schedule, start_time=start_time, end_time=end_time)
    return result


def get_maximum_retries_exceeded_records(start_time=None, end_time=None, max_retry_times=5, max_fetch_num=1000):
    ScheduleLog = get_schedule_log_model()
    failed_schedule_logs = ScheduleLog.objects.filter(create_time__lt=start_time, status__in=['X', 'T']).values(
        'queue', 'schedule_id', 'schedule_time'
    ).annotate(
        times=Count('id'),
        log_id=Max('id'),
        latest_time=Max('create_time'),
    ).filter(
        times__gte=max_retry_times,
        latest_time__gt=end_time,
    ).order_by('queue', 'schedule_id', 'schedule_time')
    return failed_schedule_logs


def get_failed_directly_records(start_time=None, end_time=None, max_retry_times=5, max_fetch_num=1000):
    ScheduleLog = get_schedule_log_model()
    failed_schedule_logs = ScheduleLog.objects.filter(create_time__lt=start_time, status=ExecuteStatus.FAILED).values(
        'queue', 'schedule_id', 'schedule_time'
    )
    return failed_schedule_logs
    # command = '''
    #             select queue, schedule_id, schedule_time, count(*) as times,
    #                 max(id) as log_id, max(create_time) as latest_time
    #             from %s where create_time > %s and status in ('X', 'T')
    #             GROUP BY queue, schedule_id, schedule_time
    #             having times >= %s and lastest_time > '%s'
    #             order by queue, schedule_id, schedule_time limit %s
    #         ''' % (ScheduleLog._meta.db_table, start_time, max_retry_times, end_time, max_fetch_num,)
    # schedules = []
    # with connection.cursor() as cursor:
    #     cursor.execute(command)
    #     for queue, schedule_id, schedule_time, times, log_id, latest_time in cursor.fetchall():
    #         schedule = Schedule(id=schedule_id, next_schedule_time=schedule_time)
    #         schedules.append(schedule)
    # return schedules


def get_retry_schedules(start_time, end_time, max_retry_times=5, max_fetch_num=1000):
    ScheduleLog = get_schedule_log_model()
    command = '''
                select queue, schedule_id, schedule_time, count(*) as times, 
                    max(id) as log_id, max(create_time) as lastest_time 
                from %s where create_time > %s and status in ('F', 'T') 
                GROUP BY queue, schedule_id, schedule_time 
                having times < %s and lastest_time > '%s' 
                order by queue, schedule_id, schedule_time limit %s
            ''' % (ScheduleLog._meta.db_table, start_time, max_retry_times, end_time, max_fetch_num,)
    with connection.cursor() as cursor:
        cursor.execute(command)
        log_ids = [str(x[4]) for x in cursor.fetchall()]
    batch_num = 1000
    i = 0
    batch = log_ids[:batch_num]
    while batch:
        command = '''
                    update %s set status = 'Q' where id in (%s)
                ''' % (ScheduleLog._meta.db_table, ','.join(batch))
        with connection.cursor() as cursor:
            cursor.execute(command)
        i += 1
        batch = log_ids[i * batch_num:(i + 1) * batch_num]