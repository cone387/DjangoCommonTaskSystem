from django_common_task_system.system_task_execution.system_task_execution.executor import (
    Executor, BaseExecutor, Failed, EmptyResult)
from django_common_task_system.builtins import builtins
import logging


logger = logging.getLogger(__name__)


@Executor.register
class StrictScheduleDaemonExecutor(BaseExecutor):
    name = builtins.tasks.strict_schedule_handle.name

    def execute(self):
        pass
