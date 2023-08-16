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


def get_log_missing_records(queue, schedule, start_time=None, end_time=None):
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
                select a.date from ({schedule_date_command}) a 
                left join (
                    select schedule_time, count(1) as log_num 
                    from {ScheduleLogModel._meta.db_table} 
                    where 
                        schedule_id = {schedule.id} and 
                        queue = '{queue}' and 
                        schedule_time between '{start_time}' and '{end_time}' 
                    group by schedule_time
                ) b 
                on a.date = b.schedule_time where b.log_num is null
            """
    time = schedule.config[schedule.config['schedule_type']].get('time', '03:00:00')
    with connection.cursor() as cursor:
        cursor.execute(command)
        for d, *_ in cursor.fetchall():
            # 根据日志查出来的遗漏日期就是实际的日期，不需要根据latest_days来计算
            if len(d) == 10:
                d = d + ' ' + time
            missing.append(parser.parse(d))
    return missing


def get_missing_schedules(queue, schedule, start_time=None, end_time=None):
    missing = []
    for schedule_time in get_log_missing_records(queue, schedule, start_time=start_time, end_time=end_time):
        o = copy.copy(schedule)
        o.next_schedule_time = schedule_time
        missing.append(o)
    return missing


def get_missing_schedules_mapping(queue, schedules,
                                  start_time=None, end_time=None):
    result = {}
    for schedule in schedules:
        result[schedule.id] = get_missing_schedules(queue, schedule, start_time=start_time, end_time=end_time)
    return result


def get_maximum_retries_exceeded_records(queue, start_time=None, end_time=None, max_retry_times=5):
    ScheduleLog = get_schedule_log_model()
    queryset = ScheduleLog.objects.filter(status__in=['X', 'T'], queue=queue)
    if start_time:
        queryset = queryset.filter(create_time__gte=start_time)
    if end_time:
        queryset = queryset.filter(create_time__lt=end_time)
    queryset = queryset.values(
        'schedule_id', 'schedule_time'
    ).annotate(
        times=Count('id'),
        log_id=Max('id'),
        latest_time=Max('create_time'),
    ).filter(
        times__gte=max_retry_times,
    ).order_by('schedule_id', 'schedule_time')
    return queryset


def get_failed_directly_records(queue, start_time=None, end_time=None):
    ScheduleLog = get_schedule_log_model()
    queryset = ScheduleLog.objects.filter(status=ExecuteStatus.FAILED, queue=queue)
    if start_time:
        queryset = queryset.filter(create_time__gte=start_time)
    if end_time:
        queryset = queryset.filter(create_time__lt=end_time)
    queryset = queryset.values('schedule_id', 'schedule_time').annotate(
        count=Count('id'),
    )
    return queryset


def get_retry_records(queue, start_time=None, end_time=None):
    # lt = less than    gt = greater than
    # lt = less than    gt = greater than
    ScheduleLog = get_schedule_log_model()
    queryset = ScheduleLog.objects.filter(status__in=['X', 'T'], queue=queue)
    if start_time:
        queryset = queryset.filter(create_time__gte=start_time)
    if end_time:
        queryset = queryset.filter(create_time__lt=end_time)
    queryset = queryset.values(
        'schedule_id', 'schedule_time'
    ).annotate(
        times=Count('id'),
        log_id=Max('id'),
        latest_time=Max('create_time'),
    ).filter(
        times__lt=5,
    ).order_by('schedule_id', 'schedule_time')
    return queryset
