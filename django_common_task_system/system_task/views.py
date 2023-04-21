from django.dispatch import receiver
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework import status
from django.db.models.signals import post_save, post_delete
from django.db import connection
from django.http.response import HttpResponse
from django_common_task_system.models import system_initialize_signal
from .models import SystemScheduleQueue, SystemSchedule, \
    SystemProcess, SystemScheduleProducer, SystemScheduleLog, SystemConsumerPermission, SystemExceptionReport
from django_common_task_system.views import TaskScheduleQueueAPI, TaskScheduleThread, ExceptionReportView
from .models import builtins
from .serializers import QueueScheduleSerializer, ExceptionSerializer
import os


builtins.initialize()


class SystemScheduleThread(TaskScheduleThread):
    schedule_model = SystemSchedule
    queues = builtins.queues
    producers = builtins.producers
    serializer = QueueScheduleSerializer


@receiver(system_initialize_signal, sender='system_initialized')
def on_system_initialized(sender, **kwargs):
    thread = SystemScheduleThread()
    thread.start()


@receiver(post_delete, sender=SystemScheduleQueue)
def delete_queue(sender, instance: SystemScheduleQueue, **kwargs):
    builtins.queues.delete(instance)


@receiver(post_save, sender=SystemScheduleQueue)
def add_queue(sender, instance: SystemScheduleQueue, created, **kwargs):
    builtins.queues.add(instance)


@receiver(post_delete, sender=SystemScheduleProducer)
def delete_producer(sender, instance: SystemScheduleProducer, **kwargs):
    builtins.producers.delete(instance)


@receiver(post_save, sender=SystemScheduleProducer)
def add_producer(sender, instance: SystemScheduleProducer, created, **kwargs):
    builtins.producers.add(instance)


@receiver(post_save, sender=SystemConsumerPermission)
def add_consumer_permission(sender, instance: SystemConsumerPermission, created, **kwargs):
    builtins.consumer_permissions.add(instance)


@receiver(post_delete, sender=SystemConsumerPermission)
def delete_consumer_permission(sender, instance: SystemConsumerPermission, **kwargs):
    builtins.consumer_permissions.delete(instance)


class ScheduleProduceView(APIView):

    def post(self, request: Request, pk: int):
        try:
            schedule = SystemSchedule.objects.get(id=pk)
        except SystemSchedule.DoesNotExist:
            return Response({'message': 'schedule_id(%s)不存在' % pk}, status=status.HTTP_404_NOT_FOUND)
        sql: str = schedule.task.config.get('sql', '').strip()
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


class SystemScheduleQueueAPI(TaskScheduleQueueAPI):

    queues = builtins.queues
    consumer_permissions = builtins.consumer_permissions
    schedule_model = SystemSchedule
    log_model = SystemScheduleLog
    serializer = QueueScheduleSerializer


class SystemProcessView:

    @staticmethod
    def show_logs(request: Request, process_id: int):
        # 此处pk为进程id
        try:
            process = SystemProcess.objects.get(process_id=process_id)
        except SystemProcess.DoesNotExist:
            return HttpResponse('SystemProcess(%s)不存在' % process_id)
        if not os.path.isfile(process.log_file):
            return HttpResponse('log文件不存在')
        offset = int(request.GET.get('offset', 0))
        with open(process.log_file, 'r', encoding='utf-8') as f:
            f.seek(offset)
            logs = f.read(offset + 1024 * 1024 * 8)
        return HttpResponse(logs, content_type='text/plain; charset=utf-8')

    @staticmethod
    def stop_process(request: Request, process_id: int):
        try:
            process = SystemProcess.objects.get(process_id=process_id)
        except SystemProcess.DoesNotExist:
            return HttpResponse('SystemProcess(%s)不存在' % process_id)
        process.delete()
        return HttpResponse('SystemProcess(%s)已停止' % process_id)


class SystemExceptionReportView(ExceptionReportView):

    queryset = SystemExceptionReport.objects.all()
    serializer_class = ExceptionSerializer
