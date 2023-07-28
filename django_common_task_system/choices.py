from django.db.models import TextChoices
import queue


class TaskStatus(TextChoices):
    ENABLE = 'E', '启用'
    DISABLE = 'D', '禁用'


class ScheduleStatus(TextChoices):
    OPENING = 'O', '开启'
    CLOSED = 'C', '关闭'
    DONE = 'D', '已完成'
    TEST = 'T', '测试'
    ERROR = 'E', '调度错误'


class ScheduleType(TextChoices):
    CRONTAB = 'C', 'Crontab'
    ONCE = 'O', '一次性'
    CONTINUOUS = 'S', '连续性'
    TIMINGS = 'T', '指定时间'


class ScheduleTimingType(TextChoices):
    DAY = 'DAY', '按天'
    WEEKDAY = 'WEEKDAY', '按周'
    MONTHDAY = 'MONTHDAY', '按月'
    YEAR = 'YEAR', "按年"
    DATETIME = 'DATETIME', '自选日期'


class ScheduleCallbackStatus(TextChoices):
    ENABLE = 'E', '启用'
    DISABLE = 'D', '禁用'


class ScheduleCallbackEvent(TextChoices):
    SUCCEED = 'S', '成功'
    FAILED = 'F', '失败'
    DONE = 'D', '完成'


class ScheduleQueueModule(TextChoices):
    FIFO = "%s.%s" % (queue.Queue.__module__, queue.Queue.__name__), '先进先出'
    STACK = "%s.%s" % (queue.LifoQueue.__module__, queue.LifoQueue.__name__), '后进先出队列'
    PRIORITY_QUEUE = "%s.%s" % (queue.PriorityQueue.__module__, queue.PriorityQueue.__name__), '优先级队列'
    SIMPLE_QUEUE = "%s.%s" % (queue.SimpleQueue.__module__, queue.SimpleQueue.__name__), '简单队列'
    REDIS_LIST_QUEUE = "django_common_task_system.queue.RedisListQueue", 'Redis List队列'


class PermissionType(TextChoices):
    IP_WHITE_LIST = 'I', 'IP白名单'


class TaskClientStatus(TextChoices):
    # start status
    INIT = 'Init', '初始化'
    PULLING = 'Pulling', '拉取镜像中'
    BUILDING = 'Building', '构建中'
    SUCCEED = 'Running', '启动成功'
    FAILED = 'Failed', '启动失败'


class ContainerStatus(TextChoices):
    NONE = 'None'
    CREATED = 'Created'
    PAUSED = 'Paused'
    RUNNING = 'Running'
    RESTARTING = 'Restarting'
    OOMKILLED = 'OOMKilled'
    DEAD = 'Dead'
    EXITED = 'Exited'


class ExecuteStatus(TextChoices):
    INIT = 'I'
    RUNNING = 'R'
    SUCCEED = 'S'
    EMPTY = 'E'
    ERROR_BUT_NO_RETRY = 'N'
    FAILED = 'F'
    DONE = 'D'
    TIMEOUT = 'T'
