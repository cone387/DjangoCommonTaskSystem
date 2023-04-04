from .base import BaseExecutor
from django_common_task_system.system_task.choices import SystemTaskType
import sys
import subprocess


class ShellExecutor(BaseExecutor):
    name = SystemTaskType.SHELL_EXECUTION.value

    def execute(self):
        if sys.platform == 'win32':
            raise RuntimeError('Windows系统不支持shell命令执行')

        commands = self.schedule.task.config.get('shell', '').split(';')
        filename = '/tmp/shell_executor.sh'
        with open('filename', 'w') as f:
            f.write('#!/bin/bash -e \n')
            f.write('; \n'.join(commands))
        p = subprocess.Popen(['/bin/bash', filename], shell=True, stdout=subprocess.PIPE)
        out, err = p.communicate()
        if err:
            raise RuntimeError(err)
        return out.decode('utf-8')
