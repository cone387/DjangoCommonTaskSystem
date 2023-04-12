from .base import BaseExecutor
from django.db import connection
from django.shortcuts import reverse
from django_common_task_system.system_task.models import builtins
import requests


class SqlExecutor(BaseExecutor):
    name = builtins.tasks.sql_execution_parent_task.name

    def execute(self):
        result = []
        commands = self.schedule.task.config.get('sql', '').split(';')
        with connection.cursor() as cursor:
            for sql in commands:
                sql = sql.strip()
                if sql:
                    cmd_result = {
                        'sql': sql,
                        'result': cursor.execute(sql)
                    }
                    result.append(cmd_result)
        return result


class SqlProduceExecutor(BaseExecutor):
    name = builtins.tasks.sql_produce_parent_task.name

    def execute(self):
        url = reverse('system_schedule_produce', args=(self.schedule.id,))
        host = self.schedule.task.config.get('host', 'http://127.0.0.1:8000')
        res = requests.post(host + url)
        return res.json()