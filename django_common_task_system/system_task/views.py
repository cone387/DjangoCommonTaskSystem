from django.dispatch import receiver
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework import status
from django.utils.module_loading import import_string
from django.db.models.signals import post_save, post_delete
from django_common_task_system.system_task.models import SystemScheduleQueue
from queue import Empty


# 后面可以改用类重写，然后可以自定义配置使用什么队列，比如redis
_system_queues = {}
try:
    for q in SystemScheduleQueue.objects.filter(status=True):
        _system_queues[q.code] = import_string(q.module)()
    _system_queue = SystemScheduleQueue.get_or_create_default()
    _system_queues[_system_queue.code] = import_string(_system_queue.module)()
except Exception as err:
    import warnings
    warnings.warn('初始化队列失败: %s' % err)


@receiver(post_delete, sender=SystemScheduleQueue)
def delete_queue(sender, instance: SystemScheduleQueue, **kwargs):
    _system_queues.pop(instance.code, None)


@receiver(post_save, sender=SystemScheduleQueue)
def add_queue(sender, instance: SystemScheduleQueue, created, **kwargs):
    if instance.code not in _system_queues:
        _system_queues[instance.code] = import_string(instance.module)()


class SystemScheduleQueueView(APIView):

    def get(self, request: Request, code: str):
        queue = _system_queues.get(code, None)
        if queue is None:
            return Response({'message': '队列(%s)不存在' % code}, status=status.HTTP_404_NOT_FOUND)
        try:
            task = queue.get_nowait()
        except Empty:
            return Response({'message': 'no schedule for %s' % code}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(task)
