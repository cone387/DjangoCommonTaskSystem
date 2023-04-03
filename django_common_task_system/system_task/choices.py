import queue
from django.db.models import TextChoices


class SystemTaskType(TextChoices):
    SQL_TASK_EXECUTION = 'SQL', 'SQL任务执行'
    SQL_TASK_PRODUCE = 'TASK_PRODUCE', 'SQL任务生产'
    SHELL_EXECUTION = 'SHELL', 'SHELL任务执行'


class ScheduleQueueModule(TextChoices):
    QUEUE = "%s.%s" % (queue.Queue.__module__, queue.Queue.__name__), '普通队列'
    STACK = "%s.%s" % (queue.LifoQueue.__module__, queue.LifoQueue.__name__), '后进先出队列'
    PRIORITY_QUEUE = "%s.%s" % (queue.PriorityQueue.__module__, queue.PriorityQueue.__name__), '优先级队列'
    SIMPLE_QUEUE = "%s.%s" % (queue.SimpleQueue.__module__, queue.SimpleQueue.__name__), '简单队列'
