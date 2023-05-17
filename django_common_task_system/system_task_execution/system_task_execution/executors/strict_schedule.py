from typing import Union
from django.urls import reverse
from .base import BaseExecutor, EmptyResult
from datetime import datetime, timedelta
from django.db import connection
from django.utils.module_loading import import_string
from django_common_task_system.choices import TaskScheduleStatus
from django_common_task_system.system_task.builtins import builtins
from django_common_task_system.models import ScheduleConfig, AbstractTaskScheduleLog, \
    AbstractTaskScheduleProducer, AbstractTaskSchedule
from django_common_task_system.system_task_execution.system_task_execution.utils import put_schedule
from urllib.parse import urljoin
from dateutil import parser
from .. import settings
import requests
import hashlib

logger = settings.logger

_cache = {}


def get_md5(value):
    value = value.encode('utf-8')
    md5 = hashlib.md5()
    md5.update(value)
    return md5.hexdigest()


def ttl(timeout=60):
    def decorator(func):
        def wrapper(*args, **kwargs):
            global _cache
            key = get_md5(func.__module__ + func.__name__ + str(args) + str(kwargs))
            content = _cache.get(key)
            if content:
                last_run_time, result = content
                if last_run_time and datetime.now() - last_run_time < timedelta(seconds=timeout):
                    return result
            result = func(*args, **kwargs)
            _cache[key] = (datetime.now(), result)
            return result
        return wrapper
    return decorator


@ttl(timeout=60)
def request_queue_status(name):
    url = urljoin(settings.HOST, reverse(name))
    res = requests.get(url)
    result = res.json()
    return result


def is_queue_free(queue, name):
    queue_status = request_queue_status(name)
    return queue_status.get(queue, 1) == 0


@ttl(timeout=60)
def request_producers(app):
    producers = []
    for p in AbstractTaskScheduleProducer.__subclasses__():
        if p._meta.app_label == app:
            producers = p.objects.filter(status=True).select_related('queue')
            break
    return producers


def get_producers_by_schedule(schedule: AbstractTaskSchedule):
    app = schedule._meta.app_label
    return request_producers(app)


def get_model_obj_value(obj, key=None):
    if not key:
        return obj
    attrs = key.split('__')
    while attrs:
        attr = attrs.pop(0)
        obj = getattr(obj, attr)
    return obj


def is_matched_production(schedule: AbstractTaskSchedule, producer: AbstractTaskScheduleProducer):
    filters: dict = producer.filters
    if not filters:
        raise Exception('producer filters is empty, please check it')
    matched = True
    for k, v in filters.items():
        matched = get_model_obj_value(schedule, k) == v
        if not matched:
            break
    return matched


def get_producer_of_schedule(schedule: AbstractTaskSchedule, producers=None) -> Union[AbstractTaskScheduleProducer, None]:
    producers = producers or get_producers_by_schedule(schedule)
    for producer in producers:
        if is_matched_production(schedule, producer):
            return producer
    return None


def get_schedule_times(schedule: AbstractTaskSchedule, start_date=None, end_date=None):
    schedule_times = []
    schedule_config = ScheduleConfig(config=schedule.config)
    if not start_date:
        update_time = schedule.config.get('update_time')
        if update_time:
            update_time = parser.parse(update_time)
        else:
            update_time = datetime.now() - timedelta(days=30)
        start_date = schedule.config[schedule.config['schedule_type']].get('schedule_start_time', None)
        if start_date:
            start_date = parser.parse(start_date)
            while start_date < update_time:
                start_date = schedule_config.get_next_time(start_date)
        else:
            start_date = update_time
    start_date = start_date or schedule.config.get('update_time', datetime.now() - timedelta(days=30))
    end_date = end_date or datetime.now()
    if isinstance(start_date, str):
        start_date = parser.parse(start_date)
    if isinstance(end_date, str):
        end_date = parser.parse(end_date)
    while True:
        start_date = schedule_config.get_next_time(start_date)
        if start_date >= end_date:
            break
        schedule_times.append(start_date)
    return schedule_times


class StrictScheduleDaemonExecutor(BaseExecutor):
    name = builtins.tasks.strict_schedule_parent_task.name

    def execute(self):
        task_config = self.schedule.task.config
        schedule_model: AbstractTaskSchedule = import_string(task_config['schedule_model'])
        schedule_log_model: AbstractTaskScheduleLog = import_string(task_config['log_model'])
        filters = task_config.get('filters', {})
        strict_start_date = task_config.get('start_date', None)
        strict_end_date = task_config.get('end_date', None)
        result = {}
        errors = {'producer_not_found': [], 'schedule_time_diff': [], 'schedule_interval': []}
        producer_not_found_errors = errors['producer_not_found']
        schedule_time_diff_errors = errors['schedule_time_diff']
        schedule_interval_errors = errors['schedule_interval']

        if self.schedule.__class__ == schedule_model:
            queue_status_url_name = 'system_schedule_status'
            handle_url_name = 'system_schedule_put'
        else:
            queue_status_url_name = 'task_schedule_status'
            handle_url_name = 'task_schedule_put'

        producers = request_producers(schedule_model._meta.app_label)
        queue_status = request_queue_status(queue_status_url_name)
        if not producers:
            raise EmptyResult('no producers found')
        free = False
        for x in queue_status.values():
            if x == 0:
                free = True
                break
        if not free:
            raise EmptyResult('no free queue found')
        queryset = schedule_model.objects.filter(
            strict_mode=True,
            status=TaskScheduleStatus.OPENING.value,
            **filters
        ).select_related(*task_config['related'])
        for strict_schedule in queryset:
            producer = get_producer_of_schedule(strict_schedule, producers=producers)
            if not producer:
                producer_not_found_errors.append(strict_schedule.id)
                continue
            queue = producer.queue.code
            qsize = queue_status.get(queue, 1)
            if qsize > 0:
                result[strict_schedule.id] = "queue(%s) %s is not free" % qsize
                continue
            strict_schedule.config['base_on_now'] = False
            schedule_times = get_schedule_times(strict_schedule, start_date=strict_start_date, end_date=strict_end_date)
            diffs = set()
            if len(schedule_times) < 2:
                info = "%s schedule times is less than 2, ignored" % strict_schedule
                result[strict_schedule.id] = info
                continue
            for i in range(len(schedule_times) - 1):
                a = schedule_times[i]
                b = schedule_times[i + 1]
                diff = b - a
                seconds = int(diff.total_seconds())
                diffs.add(seconds)
            if len(diffs) != 1:
                schedule_time_diff_errors.append(diffs)
                continue
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
                schedule_interval_errors.append("%s: %s" % (strict_schedule.id, diff))
                continue
            max_failed_times = self.schedule.task.config.get('max_failed_times', 3)
            start_date, end_date = schedule_times[0], schedule_times[-1]
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
                    select schedule_time, count(status != 'F' or null) as succeed, 
                        count(status='F' or null) as failed from {schedule_log_model._meta.db_table} where 
                        schedule_id = {strict_schedule.id} and 
                        schedule_time between '{start_date}' and '{end_date}'
                        group by schedule_time
                ) b 
                on a.date = b.schedule_time where b.succeed is null or (b.succeed = 0 and b.failed < {max_failed_times})
            """
            missing_datetimes = []
            time = strict_schedule.config[strict_schedule.config['schedule_type']].get('time', '03:00:00')
            with connection.cursor() as cursor:
                cursor.execute(command)
                for d, *_ in cursor.fetchall():
                    # 根据日志查出来的遗漏日期就是实际的日期，不需要根据latest_days来计算
                    if len(d) == 10:
                        d = d + ' ' + time
                    missing_datetimes.append(d)
            if missing_datetimes:
                logger.info("%s missing times: %s" % (strict_schedule, len(missing_datetimes)))
                url = urljoin(settings.HOST, reverse(handle_url_name))
                result[strict_schedule.id] = put_schedule(url, strict_schedule, queue, missing_datetimes)
            else:
                logger.info("%s no missing times" % strict_schedule)
        for k, v in errors.items():
            if v:
                break
        else:
            # no error
            if not result:
                raise EmptyResult("no strict schedule need to be executed")
            return result
        result['errors'] = errors
        raise ValueError(result)
