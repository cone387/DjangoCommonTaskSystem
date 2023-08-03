from datetime import datetime
from queue import Empty
from threading import Thread
from django.db import connection
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.views.decorators.csrf import csrf_exempt
from django_common_objects.models import CommonCategory
from jionlp_time import parse_time
from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from django_common_task_system.utils.foreign_key import get_model_related
from django_common_task_system.utils.schedule_time import nlp_config_to_schedule_config
from django_common_objects.rest_view import UserListAPIView, UserRetrieveAPIView
from rest_framework.request import Request
from django.http.response import JsonResponse, HttpResponse
from django_common_task_system.schedule import util as schedule_util
from .choices import TaskClientStatus, ScheduleStatus
from .client import start_client
from .models import TaskClient
from .builtins import builtins
from . import serializers, get_task_model, get_schedule_log_model, get_schedule_model, get_schedule_serializer
from . import models, system_initialized_signal
from .schedule import backend as schedule_backend
import os


UserModel = models.UserModel
TaskModel: models.Task = get_task_model()
ScheduleModel: models.Schedule = get_schedule_model()
ScheduleLogModel: models.ScheduleLog = get_schedule_log_model()
ScheduleSerializer = get_schedule_serializer()


@receiver(system_initialized_signal, sender='system_initialized')
def on_system_initialized(sender, **kwargs):
    thread = schedule_backend.TaskScheduleThread(
        schedule_model=ScheduleModel,
        schedule_serializer=ScheduleSerializer
    )
    thread.start()


@receiver(post_delete, sender=models.ScheduleQueue)
def delete_queue(sender, instance: models.ScheduleQueue, **kwargs):
    builtins.queues.delete(instance)


@receiver(post_save, sender=models.ScheduleQueue)
def add_queue(sender, instance: models.ScheduleQueue, created, **kwargs):
    builtins.queues.add(instance)


@receiver(post_save, sender=models.ScheduleProducer)
def add_producer(sender, instance: models.ScheduleProducer, created, **kwargs):
    builtins.producers.add(instance)


@receiver(post_delete, sender=models.ScheduleProducer)
def delete_producer(sender, instance: models.ScheduleProducer, **kwargs):
    builtins.producers.delete(instance)


@receiver(post_save, sender=models.ScheduleQueuePermission)
def add_schedule_queue_permission(sender, instance: models.ScheduleQueuePermission, created, **kwargs):
    builtins.schedule_queue_permissions.add(instance)


@receiver(post_delete, sender=models.ScheduleQueuePermission)
def delete_schedule_queue_permission(sender, instance: models.ScheduleQueuePermission, **kwargs):
    builtins.schedule_queue_permissions.delete(instance)


def on_system_shutdown(signum, frame):
    print('system shutdown, signal: %s' % signum)
    for client in models.TaskClient.objects.all():
        client.delete()


@receiver(post_delete, sender=TaskModel)
def delete_task(sender, instance: TaskModel, **kwargs):
    if instance.config:
        f = instance.config.get('executable_file')
        if f and os.path.exists(f):
            os.remove(f)
            path = os.path.abspath(os.path.join(f, '../'))
            if not len(os.listdir(path)):
                os.rmdir(path)


@receiver(post_save, sender=models.TaskClient)
def add_client(sender, instance: models.TaskClient, created, **kwargs):
    thread = Thread(target=start_client, args=(instance,))
    thread.start()

    """
        ValueError: signal only works in main thread of the main interpreter
        It's a known issue but apparently not documented anywhere. Sorry about that. The workaround is to run the 
        development server in single-threaded mode:
        $ python manage.py  runserver --nothreading --noreload
    """
    # for sig in [signal.SIGTERM, signal.SIGINT, getattr(signal, 'SIGQUIT', None), getattr(signal, 'SIGHUP', None)]:
    #     if sig is not None:
    #         signal.signal(sig, on_system_shutdown)


class ScheduleAPI:

    @staticmethod
    def get(request: Request, code: str):
        instance = builtins.schedule_queues.get(code, None)
        if instance is None:
            return JsonResponse({'error': '队列(%s)不存在' % code}, status=status.HTTP_404_NOT_FOUND)
        permission_validator = builtins.schedule_queue_permissions.get(code, None)
        if permission_validator is not None:
            error = permission_validator.validate(request)
            if error:
                return JsonResponse({'error': error}, status=status.HTTP_403_FORBIDDEN)
        try:
            task = instance.queue.get_nowait()
        except Empty:
            return JsonResponse({'message': 'no schedule for %s' % code}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return JsonResponse({'error': 'get schedule error: %s' % e}, status=status.HTTP_400_BAD_REQUEST)
        return JsonResponse(task)

    @staticmethod
    def get_by_id(request, pk):
        try:
            schedule = ScheduleModel.objects.get(id=pk)
            return Response(ScheduleSerializer(schedule).data)
        except ScheduleModel.DoesNotExist:
            return Response({'error': 'schedule not found'}, status=status.HTTP_404_NOT_FOUND)

    @staticmethod
    @csrf_exempt
    def retry(request):
        log_ids = request.GET.get('log-ids', None) or request.POST.get('log-ids', None)
        if not log_ids:
            return JsonResponse({'error': 'log-ids不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            log_ids = [int(i) for i in log_ids.split(',')]
            if len(log_ids) > 1000:
                raise Exception('log-ids不能超过1000个')
        except Exception as e:
            return JsonResponse({'error': 'logs_ids参数错误: %s' % e}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = {x: 'no such log' for x in log_ids}
            related = get_model_related(ScheduleLogModel, excludes=[UserModel, CommonCategory])
            logs = ScheduleLogModel.objects.filter(id__in=log_ids).select_related(*related)
            for log in logs:
                schedule = log.schedule
                queue = builtins.schedule_queues[log.queue].queue
                schedule.next_schedule_time = log.schedule_time
                schedule.generator = 'retry'
                schedule.last_log = log.result
                schedule.queue = log.queue
                data = ScheduleSerializer(schedule).data
                queue.put(data)
                result[log.id] = log.queue
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'error': '重试失败: %s' % e}, status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    @csrf_exempt
    def put(request: Request):
        schedule_ids = request.GET.get('i', None) or request.POST.get('i', None)
        queues = request.GET.get('q', None) or request.POST.get('q', None)
        schedule_times = request.GET.get('t', None) or request.POST.get('t', None)
        if not schedule_ids or not queues or not schedule_times:
            return JsonResponse({'error': 'schedule_ids(i)、queues(q)、schedule_times(t)不能为空'},
                                status=status.HTTP_400_BAD_REQUEST)
        try:
            schedule_ids = [int(i) for i in schedule_ids.split(',')]
            queues = [i.strip() for i in queues.split(',')]
            schedule_times = [datetime.strptime(i, '%Y-%m-%d %H:%M:%S') for i in schedule_times.split(',')]
            assert len(schedule_ids) <= 1000, '不能超过1000个'
            if len(queues) == 1:
                q = queues[0]
                queues = [q for _ in schedule_ids]
            elif len(queues) != len(schedule_ids):
                raise Exception('ids和queues长度不一致')
            if len(schedule_times) == 1:
                t = schedule_times[0]
                schedule_times = [t for _ in schedule_ids]
            elif len(schedule_times) != len(schedule_ids):
                raise Exception('ids和schedule_times长度不一致')
        except Exception as e:
            return JsonResponse({'error': 'ids参数错误: %s' % e}, status=status.HTTP_400_BAD_REQUEST)
        try:
            schedules = ScheduleModel.objects.filter(id__in=set(schedule_ids))
            schedule_mapping = {x.id: x for x in schedules}
            result = {}
            for i, q, t in zip(schedule_ids, queues, schedule_times):
                queue_instance = builtins.schedule_queues.get(q, None)
                if queue_instance is None:
                    result[q] = 'no such queue: %s' % q
                    continue
                queue_result = result.setdefault(q, {})
                schedule = schedule_mapping.get(i, None)
                if schedule is None:
                    queue_result[i] = 'no such schedule: %s' % i
                    continue
                schedule_result = queue_result.setdefault(i, [])
                schedule.next_schedule_time = t
                schedule.generator = 'put'
                schedule.queue = q
                data = ScheduleSerializer(schedule).data
                queue_instance.queue.put(data)
                schedule_result.append(t.strftime('%Y-%m-%d %H:%M:%S'))
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'error': '添加到队列失败: %s' % e}, status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    def status(request):
        return JsonResponse({x: y.queue.qsize() for x, y in builtins.schedule_queues.items()})

    @staticmethod
    def get_missing_schedules(request):
        schedule_id = request.GET.get('schedule_id')
        is_strict = request.GET.get('strict', '1') == '1'
        if schedule_id:
            schedules = ScheduleModel.objects.filter(id=schedule_id, status=ScheduleStatus.OPENING.value)
        else:
            schedules = ScheduleModel.objects.filter(is_strict=is_strict, status=ScheduleStatus.OPENING.value)
        missing_result = schedule_util.get_missing_schedules(schedules)
        missing = []
        for pk, target in missing_result.items():
            missing.extend(target)
        return JsonResponse(ScheduleSerializer(missing, many=True).data)


class ScheduleProduceView(APIView):

    def post(self, request: Request, pk: int):
        try:
            schedule = ScheduleModel.objects.select_related('task').get(id=pk)
        except ScheduleModel.DoesNotExist:
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


class ScheduleTimeParseView(APIView):

    def get(self, request, *args, **kwargs):
        sentence = request.query_params.get('sentence')
        if not sentence:
            return Response({'error': 'sentence is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = parse_time(sentence)
            schedule = nlp_config_to_schedule_config(result, sentence=sentence)
            return Response({
                "jio_result": result,
                "schedule": schedule
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TaskClientView:

    @staticmethod
    def show_logs(request: Request, client_id: int):
        # 此处pk为进程id
        client: TaskClient = TaskClient.objects.get(client_id)
        if client is None:
            return HttpResponse('TaskClient(%s)不存在' % client_id)
        if client.startup_status != TaskClientStatus.SUCCEED:
            return HttpResponse(client.startup_log, content_type='text/plain; charset=utf-8')
        logs = client.container.logs(tail=1000)
        return HttpResponse(logs, content_type='text/plain; charset=utf-8')

    @staticmethod
    def stop_process(request: Request, client_id: int):
        client = TaskClient.objects.get(pk=client_id)
        if client is None:
            return HttpResponse('TaskClient(%s)不存在' % client_id)
        try:
            client.delete()
            return HttpResponse('TaskClient(%s)已停止' % client_id)
        except Exception as e:
            return HttpResponse('停止TaskClient(%s)失败: %s' % (client_id, e))


class TaskListView(UserListAPIView):
    queryset = TaskModel.objects.all()
    serializer_class = serializers.TaskSerializer


class TaskDetailView(UserRetrieveAPIView):
    queryset = TaskModel.objects.all()
    serializer_class = serializers.TaskSerializer


class ScheduleListView(UserListAPIView):
    queryset = ScheduleModel.objects.all()
    serializer_class = serializers.ScheduleSerializer


class ScheduleDetailView(UserRetrieveAPIView):
    queryset = ScheduleModel.objects.all()
    serializer_class = serializers.ScheduleSerializer


class ScheduleLogViewSet(ModelViewSet):
    queryset = ScheduleLogModel.objects.all()
    serializer_class = serializers.ScheduleLogSerializer


class ExceptionReportView(CreateAPIView):
    queryset = models.ExceptionReport.objects.all()
    serializer_class = serializers.ExceptionSerializer

    def perform_create(self, serializer):
        meta = self.request.META
        group = self.request.POST.get('group')
        if not group:
            url_name = self.request.stream.resolver_match.url_name
            if url_name == 'exception-report':
                group = 'user'
            elif url_name == 'exception-report':
                group = 'system'
            else:
                group = url_name
        ip = meta.get('HTTP_X_FORWARDED_FOR') if meta.get('HTTP_X_FORWARDED_FOR') else meta.get('REMOTE_ADDR')
        serializer.save(ip=ip, group=group)
