from .base import BaseExecutor, EmptyResult
from django.db import connection
from django.shortcuts import reverse
from .. import settings
from urllib.parse import urljoin
from django_common_task_system.system_task.builtins import builtins
import requests


class SqlExecutor(BaseExecutor):
    name = builtins.tasks.sql_execution_parent_task.name

    def execute(self):
        result = []
        commands = self.schedule.task.config.get('script', '').split(';')
        with connection.cursor() as cursor:
            for sql in commands:
                sql = sql.strip()
                if sql:
                    cmd_result = {
                        'script': sql,
                        'result': cursor.execute(sql)
                    }
                    result.append(cmd_result)
        return result


class SqlProduceExecutor(BaseExecutor):
    name = builtins.tasks.sql_produce_parent_task.name

    def execute(self):
        url = reverse('system_schedule_produce', args=(self.schedule.id,))
        res = requests.post(urljoin(settings.HOST, url))
        if res.status_code != 200:
            raise Exception('produce failed: %s' % res.text)
        result = res.json()
        nums = result.get('nums', 0)
        if nums == 0:
            raise EmptyResult('produce failed: %s' % res.text)
        return result
