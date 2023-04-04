from . shell import ShellExecutor
from . sql import SqlExecutor, SqlProduceExecutor


Executors = {
    SqlExecutor.name: SqlExecutor,
    SqlProduceExecutor.name: SqlProduceExecutor,
    ShellExecutor.name: ShellExecutor,
}
