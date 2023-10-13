from django.db import connection as django_connection
from django_common_task_system.builtins import builtins
from django_common_task_system.system_task_execution.system_task_execution.consumer import (
    Executor, BaseExecutor, Failed)
import pymysql


@Executor.register
class SQLExecutor(BaseExecutor):
    parent = builtins.tasks.sql_execution.name

    def execute(self):
        result = []
        commands = self.schedule.task.config.get('script', '').strip().split(';')
        sql_config = self.schedule.task.config.get('sql_config') or {}
        host = sql_config.get('host')
        if host:
            connection = pymysql.connect(**sql_config)
        else:
            connection = django_connection
        with connection.cursor() as cursor:
            for sql in commands:
                sql = sql.strip()
                if sql:
                    if sql.lower().startswith('select'):
                        cursor.execute(sql)
                        cmd_result = {
                            'script': sql,
                            'result': cursor.fetchall()
                        }
                    elif sql.lower().startswith('replace'):
                        # 需要允许执行select语句，比如会有insert into select语句的场景
                        raise Failed('replace not support')
                    else:
                        cmd_result = {
                            'script': sql,
                            'result': cursor.execute(sql)
                        }
                    result.append(cmd_result)
        return result
