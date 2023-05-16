from typing import Union
from django.urls import reverse
from .base import BaseExecutor
from datetime import datetime, timedelta
from django.db import connection
from django.utils.module_loading import import_string
from django_common_task_system.choices import TaskScheduleStatus
from django_common_task_system.system_task.builtins import builtins
from django_common_task_system.models import ScheduleConfig, AbstractTaskScheduleLog, \
    AbstractTaskScheduleProducer, AbstractTaskSchedule
from django_common_task_system.system_task_execution.system_task_execution.utils import put_schedule
from urllib.parse import urljoin
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


def get_producer_of_schedule(schedule: AbstractTaskSchedule) -> Union[AbstractTaskScheduleProducer, None]:
    producers = get_producers_by_schedule(schedule)
    for producer in producers:
        if is_matched_production(schedule, producer):
            return producer
    return None


def get_schedule_times(schedule: AbstractTaskSchedule, start_date=None, end_date=None):
    start_date = start_date or schedule.config.get('update_time', datetime.now() - timedelta(days=30))
    end_date = end_date or datetime.now()
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
    schedule_times = []
    schedule_config = ScheduleConfig(config=schedule.config)
    while start_date < end_date:
        start_date = schedule_config.get_next_time(start_date)
        schedule_times.append(start_date)
    return schedule_times


class StrictScheduleDaemonExecutor(BaseExecutor):
    name = builtins.tasks.strict_schedule_parent_task.name
    handle_url = 'system_schedule_put'

    def execute(self):
        task_config = self.schedule.task.config
        schedule_model: AbstractTaskSchedule = import_string(task_config['model'])
        for model in AbstractTaskScheduleLog.__subclasses__():
            if schedule_model == model.schedule.field.related_model:
                schedule_log_model = model
                break
        else:
            raise ValueError("schedule log model not found for %s" % schedule_model)
        result = {}
        error = None
        if self.schedule.__class__ == schedule_model:
            queue_status_url_name = 'system_schedule_status'
        else:
            queue_status_url_name = 'task_schedule_status'
        for strict_schedule in schedule_model.objects.filter(
            strict_mode=True,
            status=TaskScheduleStatus.OPENING.value,
        ):
            producer = get_producer_of_schedule(strict_schedule)
            if not producer:
                error = "producer not found for %s" % strict_schedule
                result[strict_schedule.id] = error
                continue
            queue = producer.queue.code
            if not is_queue_free(queue, name=queue_status_url_name):
                result[strict_schedule.id] = "queue %s is not free" % queue
                continue
            strict_schedule.config['base_on_now'] = False
            schedule_times = get_schedule_times(strict_schedule)
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
                error = "schedule times diff is not same for %s" % strict_schedule
                result[strict_schedule.id] = error
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
                error = "unsupported interval: %s" % diff
                result[strict_schedule.id] = error
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
                    select schedule_time, count(status='S' or null) as succeed, 
                        count(status='F' or null) as failed from {schedule_log_model._meta.db_table} where 
                        schedule_id = {strict_schedule.id} and 
                        schedule_time between '{start_date}' and '{end_date}'
                        group by schedule_time
                ) b on a.date = b.schedule_time where b.succeed = 0 or b.failed > {max_failed_times}
            """
            missing_datetimes = []
            time = strict_schedule.config[strict_schedule.config['schedule_type']].get('time', '03:00:00')
            with connection.cursor() as cursor:
                cursor.execute(command)
                for d in cursor.fetchall():
                    # 根据日志查出来的遗漏日期就是实际的日期，不需要根据latest_days来计算
                    if len(d) == 10:
                        d = d + ' ' + time
                    missing_datetimes.append(d)
            if missing_datetimes:
                logger.info("%s missing times: %s" % (strict_schedule, len(missing_datetimes)))
                url = urljoin(settings.HOST, reverse(self.handle_url))
                result[strict_schedule.id] = put_schedule(url, strict_schedule, queue, missing_datetimes)
            else:
                logger.info("%s no missing times" % strict_schedule)
        if error:
            raise ValueError(error)
        return result