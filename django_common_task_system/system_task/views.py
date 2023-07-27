from django.dispatch import receiver
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework import status
from django.db.models.signals import post_save, post_delete
from django.db import connection
from rest_framework.viewsets import ModelViewSet
from .models import (ScheduleQueue, SystemSchedule, ScheduleProducer,
                     SystemScheduleLog, ScheduleConsumerPermission, ExceptionReport, SystemTask)
from django_common_task_system.generic import views as generic_views, system_initialize_signal
from django_common_task_system.generic import schedule_backend
from .builtins import builtins
from . import serializers
import os


@receiver(system_initialize_signal, sender='system_initialized')
def on_system_initialized(sender, **kwargs):
    thread = schedule_backend.TaskScheduleThread(
        schedule_model=SystemSchedule,
        builtins=builtins,
        schedule_serializer=serializers.QueueScheduleSerializer
    )
    thread.start()


@receiver(post_delete, sender=ScheduleQueue)
def delete_queue(sender, instance: ScheduleQueue, **kwargs):
    builtins.queues.delete(instance)


@receiver(post_save, sender=ScheduleQueue)
def add_queue(sender, instance: ScheduleQueue, created, **kwargs):
    builtins.queues.add(instance)


@receiver(post_delete, sender=ScheduleProducer)
def delete_producer(sender, instance: ScheduleProducer, **kwargs):
    builtins.producers.delete(instance)


@receiver(post_save, sender=ScheduleProducer)
def add_producer(sender, instance: ScheduleProducer, created, **kwargs):
    builtins.producers.add(instance)


@receiver(post_save, sender=ScheduleConsumerPermission)
def add_consumer_permission(sender, instance: ScheduleConsumerPermission, created, **kwargs):
    builtins.consumer_permissions.add(instance)


@receiver(post_delete, sender=ScheduleConsumerPermission)
def delete_consumer_permission(sender, instance: ScheduleConsumerPermission, **kwargs):
    builtins.consumer_permissions.delete(instance)


@receiver(post_delete, sender=SystemTask)
def delete_task(sender, instance: SystemTask, **kwargs):
    if instance.config:
        f = instance.config.get('executable_file')
        if f and os.path.exists(f):
            os.remove(f)
            path = os.path.abspath(os.path.join(f, '../'))
            if not len(os.listdir(path)):
                os.rmdir(path)


class ScheduleProduceView(APIView):

    def post(self, request: Request, pk: int):
        try:
            schedule = SystemSchedule.objects.select_related('task').get(id=pk)
        except SystemSchedule.DoesNotExist:
            return Response({'message': 'schedule_id(%s)不存在' % pk}, status=status.HTTP_404_NOT_FOUND)
        sql: str = schedule.task.config.get('script', '').strip()
        if not sql:
            return Response({'message': 'sql语句不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        if not sql.startswith('select'):
            return Response({'message': 'sql语句必须以select开头'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            queue = builtins.queues[schedule.task.config['queue']].queue
            max_size = schedule.task.config.get('max_size', 10000)
            if queue.qsize() > max_size:
                return Response({'message': '队列(%s)已满(%s)' % (schedule.task.config['queue'], max_size)},
                                status=status.HTTP_400_BAD_REQUEST)
            schedule.task.name = schedule.task.name + "-生产的任务"
            if schedule.task.config.get('include_meta'):
                def produce(item):
                    schedule.task.config['content'] = item
                    queue.put(serializers.QueueScheduleSerializer(schedule).data)
            else:
                def produce(item):
                    item['task_name'] = schedule.task.name
                    queue.put(item)
            with connection.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
                col_names = [desc[0] for desc in cursor.description]
                nums = len(rows)
                for row in rows:
                    obj = {}
                    for index, value in enumerate(row):
                        obj[col_names[index]] = value
                    produce(obj)
        except Exception as e:
            return Response({'message': 'sql语句执行失败: %s' % e}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': '成功产生%s条数据' % nums, 'nums': nums})


class ExceptionReportView(generic_views.ExceptionReportView):
    queryset = ExceptionReport.objects.all()
    serializer_class = serializers.ExceptionSerializer


class ScheduleLogViewSet(ModelViewSet):
    queryset = SystemScheduleLog.objects.all()
    serializer_class = serializers.TaskScheduleLogSerializer


SystemScheduleQueueAPI = generic_views.TaskScheduleQueueAPI(
    schedule_mode=SystemSchedule,
    log_model=SystemScheduleLog,
    queues=builtins.queues,
    serializer=serializers.QueueScheduleSerializer,
    consumer_permissions=builtins.consumer_permissions,
)
