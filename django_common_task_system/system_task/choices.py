# import queue
# from django.db.models import TextChoices
#
#
# class ScheduleQueueModule(TextChoices):
#     QUEUE = "%s.%s" % (queue.Queue.__module__, queue.Queue.__name__), '普通队列'
#     STACK = "%s.%s" % (queue.LifoQueue.__module__, queue.LifoQueue.__name__), '后进先出队列'
#     PRIORITY_QUEUE = "%s.%s" % (queue.PriorityQueue.__module__, queue.PriorityQueue.__name__), '优先级队列'
#     SIMPLE_QUEUE = "%s.%s" % (queue.SimpleQueue.__module__, queue.SimpleQueue.__name__), '简单队列'
#     REDIS_LIST_QUEUE = "django_common_task_system.system_task.queue.RedisListQueue", 'Redis List队列'
