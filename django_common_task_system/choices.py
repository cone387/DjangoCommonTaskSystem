from django.db.models import TextChoices, IntegerChoices


class TaskStatus(TextChoices):
    ENABLE = 'E', '启用'
    DISABLE = 'D', '禁用'


class ScheduleStatus(TextChoices):
    OPENING = 'O', '开启'
    AUTO = 'A', '自动'
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


# if os.environ.get('USE_GUNICORN', None) == 'true':
#     # 当使用gunicorn时，需要使用redis作为队列, 或者其它支持多进程的队列
#     class ScheduleQueueModule(TextChoices):
#         FIFO = "django_common_task_system.queue.RedisListQueue", 'Redis先进先出队列'
#         LIFO = "django_common_task_system.queue.RedisListQueue", 'Redis后进先出队列'
# else:
class ScheduleQueueModule(TextChoices):

    @staticmethod
    def get_default():
        return "django_common_task_system.queue.SocketQueue"

    DEFAULT = get_default(), '先进先出队列'
    # PRIORITY_QUEUE = "%s.%s" % (queue.PriorityQueue.__module__, queue.PriorityQueue.__name__), '优先级队列'
    # SIMPLE_QUEUE = "%s.%s" % (queue.SimpleQueue.__module__, queue.SimpleQueue.__name__), '简单队列'
    REDIS_FIFO = "django_common_task_system.queue.redis.RedisFIFOQueue", 'Redis先进先出队列'
    REDIS_LIFO = "django_common_task_system.queue.redis.RedisLIFOQueue", 'Redis后进先出队列'
    # MULTIPROCESS_QUEUE = "multiprocessing.Queue", '多进程队列'


class PermissionType(TextChoices):
    IP_WHITE_LIST = 'I', 'IP白名单'


class ProgramType(IntegerChoices):
    DOCKER = 1, 'Docker'
    PROCESS = 2, '进程'


class ConsumerSource(IntegerChoices):
    REPORT = 1, '主动上报'
    DETECT = 2, '被动检测'
    ADMIN = 3, '管理员添加'
    API = 4, 'API添加'


class ConsumerStatus(IntegerChoices):
    # start status
    # INIT = 'Init', '初始化'
    # PULLING = 'Pulling', '拉取镜像中'
    # BUILDING = 'Building', '构建中'
    # STOPPING = 'Stopping', '停止中'
    # STOPPED = 'Stopped', '已停止'
    # RUNNING = 'Running', '启动成功'
    # FAILED = 'Failed', '启动失败'
    CREATED = 1, '已创建'
    RUNNING = 2, '运行中'
    STOPPED = 3, '已停止'
    FAILED = 4, '消费失败'


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
    INIT = 'I', '初始化'
    RUNNING = 'R', '运行中'
    SUCCEED = 'S', '运行成功'
    EMPTY = 'E', '执行成功了，结果为空'
    NO_RETRY = 'N', '无需重试的异常'
    EXCEPTION = 'X', '运行异常'
    PARTIAL_FAILED = 'P', '部分失败'
    FAILED = 'F', '任务失败, 无需重试'
    TIMEOUT = 'T', '超时'


class ScheduleExceptionReason(TextChoices):
    FAILED_DIRECTLY = 'FAILED_DIRECTLY', '执行失败'
    SCHEDULE_LOG_NOT_FOUND = 'SCHEDULE_LOG_NOT_FOUND', '缺失成功的计划日志'
    MAXIMUM_RETRIES_EXCEEDED = 'MAXIMUM_RETRIES_EXCEEDED', '超过最大重试次数'
    # OTHER = 'OTHER', '其他'
