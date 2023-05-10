import json
import re
from typing import Union
from django.urls import reverse
from .base import BaseExecutor
from datetime import datetime, timedelta
from django.db import connection
from django_common_task_system.system_task.models import builtins
from django_common_task_system.models import ScheduleConfig, AbstractTaskScheduleLog, \
    AbstractTaskScheduleProducer, AbstractTaskSchedule
from django_common_task_system.system_task_execution.system_task_execution.utils import put_schedule, to_model
from urllib.parse import urljoin
from .. import settings

logger = settings.logger


_producers = {}


def get_producers_by_schedule(schedule: AbstractTaskSchedule):
    global _producers
    # 根据schedule所在app找到对应的producer
    app = schedule._meta.app_label
    producers = _producers.get(app)
    if not producers:
        for p in AbstractTaskScheduleProducer.__subclasses__():
            if p._meta.app_label == app:
                _producers[app] = p.objects.filter(status=True).select_related('queue')
                break
    return _producers[app]


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
    names = [getattr(v, 'name') + '-生产的任务' for k, v in builtins.tasks.__dict__.items() if k.startswith('strict_')]
    handle_url = 'system_schedule_put'

    def execute(self):
        task_config = self.schedule.task.config
        table = re.search(r'from *?(\w+) *?where', task_config['script']).group(1)
        for model in AbstractTaskSchedule.__subclasses__():
            if model._meta.db_table == table:
                schedule_model = model
                break
        else:
            raise ValueError("schedule model not found for %s" % table)
        # task content为要处理的strict_schedule的配置
        strict_schedule = to_model(task_config['content'], schedule_model)
        strict_schedule.config = json.loads(strict_schedule.config)
        for model in AbstractTaskScheduleLog.__subclasses__():
            if schedule_model == model.schedule.field.related_model:
                schedule_log_model = model
                break
        else:
            raise ValueError("schedule log model not found for %s" % schedule_model)
        producer = get_producer_of_schedule(strict_schedule)
        if not producer:
            raise ValueError("producer not found for %s" % strict_schedule)
        queue = producer.queue.code
        strict_schedule.config['base_on_now'] = False
        schedule_times = get_schedule_times(strict_schedule)
        diffs = set()
        if len(schedule_times) < 2:
            return "%s schedule times is less than 2, ignored" % strict_schedule
        for i in range(len(schedule_times) - 1):
            a = schedule_times[i]
            b = schedule_times[i + 1]
            diff = b - a
            seconds = int(diff.total_seconds())
            diffs.add(seconds)
        assert len(diffs) == 1, "schedule time interval is not equal, diffs: %s" % diffs
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
            raise TypeError("unsupported interval: %s" % diff)
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
            return put_schedule(url, strict_schedule, queue, missing_datetimes)
        return missing_datetimes
