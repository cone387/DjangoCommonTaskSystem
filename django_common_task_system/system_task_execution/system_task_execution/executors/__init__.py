from . shell import ShellExecutor
from . sql import SqlExecutor, SqlProduceExecutor
from .exception import SystemExceptionExecutor, ScheduleExceptionExecutor
from .strict_schedule import StrictScheduleDaemonExecutor


Executors = {
    SqlExecutor.name: SqlExecutor,
    SqlProduceExecutor.name: SqlProduceExecutor,
    ShellExecutor.name: ShellExecutor,
    SystemExceptionExecutor.name: SystemExceptionExecutor,
    ScheduleExceptionExecutor.name: ScheduleExceptionExecutor,
    StrictScheduleDaemonExecutor.name: StrictScheduleDaemonExecutor,
}
