from django.dispatch import receiver
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework import status
from django.utils.module_loading import import_string
from django.db.models.signals import post_save, post_delete
from django.db import connection
from django_common_task_system import serializers
from django_common_task_system.system_task.choices import SystemTaskType
from django_common_task_system.system_task.models import SystemScheduleQueue, SystemSchedule, SystemScheduleLog
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


def get_schedule_queue(schedule: SystemSchedule):
    return _system_queues[_system_queue.code]


@receiver(post_delete, sender=SystemScheduleQueue)
def delete_queue(sender, instance: SystemScheduleQueue, **kwargs):
    _system_queues.pop(instance.code, None)


@receiver(post_save, sender=SystemScheduleQueue)
def add_queue(sender, instance: SystemScheduleQueue, created, **kwargs):
    if instance.status and instance.code not in _system_queues:
        _system_queues[instance.code] = import_string(instance.module)()
    elif not instance.status:
        _system_queues.pop(instance.code, None)


class ScheduleProduceView(APIView):

    def post(self, request: Request, pk: int):
        try:
            schedule = SystemSchedule.objects.get(id=pk, task__task_type=SystemTaskType.SQL_TASK_PRODUCE)
        except SystemSchedule.DoesNotExist:
            return Response({'message': 'schedule_id(%s)不存在' % pk}, status=status.HTTP_404_NOT_FOUND)
        sql: str = schedule.task.config.get('sql', '').strip()
        if not sql:
            return Response({'message': 'sql语句不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        if not sql.startswith('select'):
            return Response({'message': 'sql语句必须以select开头'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            queue = _system_queues[schedule.task.config['queue']]
            max_size = schedule.task.config.get('max_size', 10000)
            if queue.qsize() > max_size:
                return Response({'message': '队列(%s)已满(%s)' % (schedule.task.config['queue'], max_size)},
                                status=status.HTTP_400_BAD_REQUEST)
            with connection.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
                col_names = [desc[0] for desc in cursor.description]
                nums = len(rows)
                for row in rows:
                    obj = {}
                    for index, value in enumerate(row):
                        obj[col_names[index]] = value
                    queue.put(obj)
        except Exception as e:
            return Response({'message': 'sql语句执行失败: %s' % e}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': '成功产生%s条数据' % nums})


class SystemScheduleQueueAPI:

    @staticmethod
    @api_view(['GET'])
    def get(request: Request, code: str):
        queue = _system_queues.get(code, None)
        if queue is None:
            return Response({'message': '队列(%s)不存在' % code}, status=status.HTTP_404_NOT_FOUND)
        try:
            task = queue.get_nowait()
        except Empty:
            return Response({'message': 'no schedule for %s' % code}, status=status.HTTP_204_NO_CONTENT)
        return Response(task)

    @staticmethod
    @api_view(['GET'])
    def retry(request: Request, pk: int):
        try:
            # 重试失败的任务, 这里的pk应该是schedule_log的id，schedule是会变的
            log = SystemScheduleLog.objects.get(id=pk)
        except SystemScheduleLog.DoesNotExist:
            return Response({'error': 'sys_schedule_log_id(%s)不存在, 重试失败' % pk}, status=status.HTTP_404_NOT_FOUND)
        try:
            queue = get_schedule_queue(log.schedule)
            queue.put(serializers.QueueScheduleSerializer(log.schedule).data)
            return Response({'message': '成功添加到重试队列'})
        except Exception as e:
            return Response({'error': '重试失败: %s' % e}, status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    @api_view(['GET'])
    def put(request: Request, pk: int):
        try:
            schedule = SystemSchedule.objects.get(id=pk)
        except SystemSchedule.DoesNotExist:
            return Response({'error': 'sys_schedule_id(%s)不存在, 重试失败' % pk}, status=status.HTTP_404_NOT_FOUND)
        try:
            queue = get_schedule_queue(schedule)
            queue.put(serializers.QueueScheduleSerializer(schedule).data)
            return Response({'message': '成功添加到队列'})
        except Exception as e:
            return Response({'error': '添加到队列失败: %s' % e}, status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    @api_view(['GET'])
    def status(request: Request):
        data = {
            k: v.qsize() for k, v in _system_queues.items()
        }
        return Response(data)
