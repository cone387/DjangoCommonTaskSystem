from datetime import datetime
from queue import Empty
from django.db import connection
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django_common_objects.models import CommonCategory
from jionlp_time import parse_time
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound
from rest_framework.generics import CreateAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from django_common_task_system.utils.foreign_key import get_model_related
from django_common_task_system.utils.schedule_time import nlp_config_to_schedule_config
from django_common_objects.rest_view import UserListAPIView, UserRetrieveAPIView
from rest_framework.request import Request
from django.http.response import HttpResponse
from django_common_task_system.schedule import util as schedule_util
from django_common_task_system.producer import producer_agent
from django_common_task_system.system_task_execution import consumer_agent
from django_common_task_system.program import ProgramAction, ProgramAgent
from .choices import TaskClientStatus, ScheduleStatus
from .models import Consumer
from .builtins import builtins
from . import serializers, get_task_model, get_schedule_log_model, get_schedule_model, get_schedule_serializer
from . import models, system_initialized_signal
from . import consumer
from .log import PagedLog
from typing import List, Dict, Union
import os


User = models.UserModel
Task: models.Task = get_task_model()
Schedule: models.Schedule = get_schedule_model()
ScheduleLog: models.ScheduleLog = get_schedule_log_model()
ScheduleSerializer = get_schedule_serializer()


# @receiver(system_initialized_signal, sender='system_initialized')
# def on_system_initialized(sender, **kwargs):
#     schedule_client.start_system_process()
#     schedule_client.start_schedule_thread()


def on_system_shutdown(signum, frame):
    print('system shutdown, signal: %s' % signum)
    for client in models.TaskClient.objects.all():
        client.delete()


@receiver(post_delete, sender=models.ScheduleQueue)
def delete_queue(sender, instance: models.ScheduleQueue, **kwargs):
    builtins.schedule_queues.delete(instance)


@receiver(post_save, sender=models.ScheduleQueue)
def add_queue(sender, instance: models.ScheduleQueue, created, **kwargs):
    builtins.schedule_queues.add(instance)


@receiver(post_save, sender=models.ScheduleProducer)
def add_producer(sender, instance: models.ScheduleProducer, created, **kwargs):
    builtins.schedule_producers.add(instance)


@receiver(post_delete, sender=models.ScheduleProducer)
def delete_producer(sender, instance: models.ScheduleProducer, **kwargs):
    builtins.schedule_producers.delete(instance)


@receiver(post_save, sender=models.ScheduleQueuePermission)
def add_schedule_queue_permission(sender, instance: models.ScheduleQueuePermission, created, **kwargs):
    builtins.schedule_queue_permissions.add(instance)


@receiver(post_delete, sender=models.ScheduleQueuePermission)
def delete_schedule_queue_permission(sender, instance: models.ScheduleQueuePermission, **kwargs):
    builtins.schedule_queue_permissions.delete(instance)


@receiver(post_delete, sender=Task)
def delete_task(sender, instance: Task, **kwargs):
    if instance.config:
        f = instance.config.get('executable_file')
        if f and os.path.exists(f):
            os.remove(f)
            path = os.path.abspath(os.path.join(f, '../'))
            if not len(os.listdir(path)):
                os.rmdir(path)


@receiver(post_save, sender=models.Consumer)
def add_client(sender, instance: models.Consumer, created, **kwargs):
    # thread = Thread(target=schedule_client.start_client, args=(instance,))
    # thread.start()
    consumer.consume(instance)
    """
        ValueError: signal only works in main thread of the main interpreter
        It's a known issue but apparently not documented anywhere. Sorry about that. The workaround is to run the 
        development server in single-threaded mode:
        $ python manage.py  runserver --nothreading --noreload
    """

# for sig in [signal.SIGTERM, signal.SIGINT, getattr(signal, 'SIGQUIT', None), getattr(signal, 'SIGHUP', None)]:
#     if sig is not None:
#         signal.signal(sig, on_system_shutdown)


def retry_from_log_ids(log_ids: List[int]):
    result = {x: 'no such log' for x in log_ids}
    related = get_model_related(ScheduleLog, excludes=[User, CommonCategory])
    logs = ScheduleLog.objects.filter(id__in=log_ids).select_related(*related)
    for log in logs:
        schedule = log.schedule
        queue = builtins.schedule_queues[log.queue].queue
        schedule.next_schedule_time = log.schedule_time
        schedule.generator = 'retry'
        schedule.last_log = log.result
        schedule.queue = log.queue
        data = ScheduleSerializer(schedule).data
        queue.put(data)
        result[log.id] = "%s->%s" % (schedule.id, log.queue)
    return result


ScheduleRecord = Dict[str, Dict[str, List[str]]]


def put_schedules(records: ScheduleRecord):
    schedules = Schedule.objects.filter(id__in=records.keys())
    schedule_mapping = {str(x.id): x for x in schedules}
    result: Dict[str, Union[Dict[str, str], str]] = {}
    for schedule_id, record in records.items():
        schedule = schedule_mapping.get(schedule_id, None)
        if schedule is None:
            result[schedule_id] = 'no such schedule'
        else:
            schedule_result = result.setdefault(schedule_id, {})
            for queue, schedule_times in record.items():
                schedule_queue = builtins.schedule_queues.get(queue, None)
                if schedule_queue is None:
                    schedule_result[queue] = 'no such queue'
                    continue
                queue_instance = schedule_queue.queue
                for schedule_time in schedule_times:
                    schedule.next_schedule_time = schedule_time
                    schedule.generator = 'put'
                    schedule.queue = queue
                    data = ScheduleSerializer(schedule).data
                    queue_instance.put(data)
                schedule_result[queue] = "%s schedule(s) put" % len(schedule_times)
    return result


class ScheduleAPI:

    @staticmethod
    @api_view(['GET'])
    def get(request: Request, code: str):
        instance = builtins.schedule_queues.get(code, None)
        if instance is None:
            return Response({'error': '队列(%s)不存在' % code}, status=status.HTTP_404_NOT_FOUND)
        permission_validator = builtins.schedule_queue_permissions.get(code, None)
        if permission_validator is not None:
            error = permission_validator.validate(request)
            if error:
                return Response({'error': error}, status=status.HTTP_403_FORBIDDEN)
        try:
            schedule = instance.queue.get_nowait()
        except Empty:
            return Response({'message': 'no schedule for %s' % code}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({'error': 'get schedule error: %s' % e}, status=status.HTTP_400_BAD_REQUEST)
        return Response(schedule)

    @staticmethod
    @csrf_exempt
    @api_view(['GET', 'POST'])
    def retry(request: Request):
        log_ids = request.data
        if not log_ids:
            log_ids = request.GET.get('log-ids', '')
            try:
                log_ids = [int(i) for i in log_ids.split(',')]
                if len(log_ids) > 1000:
                    raise Exception('log-ids不能超过1000个')
            except ValueError:
                return Response({'error': 'log-id为int'}, status=status.HTTP_400_BAD_REQUEST)
        if not log_ids:
            return Response({'error': 'log-ids不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            return Response(retry_from_log_ids(log_ids))
        except Exception as e:
            return Response({'error': '重试失败: %s' % e}, status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    @csrf_exempt
    @api_view(["GET", 'POST'])
    def put(request: Request):
        data: List[List[str, str, str]] = request.data
        records = {}
        try:
            if not data:
                data = [request.query_params.get('data', '').split(',')]
            for i, q, t in data:
                records.setdefault(i, {}).setdefault(q, []).append(datetime.strptime(t, '%Y%m%d%H%M%S'))
        except Exception as e:
            return Response({'error': 'data参数错误: %s, 参数格式: %s' % (e, '[[schedule_id, queue, schedule_time]]')},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            return Response(put_schedules(records))
        except Exception as e:
            return Response({'error': 'put failed: %s' % e}, status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    @csrf_exempt
    @api_view(['POST'])
    def put_raw(request: Request):
        schedules: List[Dict] = request.data['schedules']
        queue = request.data['queue']
        queue_instance = getattr(builtins.schedule_queues.get(queue, None), 'queue', None)
        if queue_instance is None:
            return Response({'error': '队列(%s)不存在' % queue}, status=status.HTTP_404_NOT_FOUND)
        check_fields = ['schedule_time', 'task', 'id', 'queue']
        for i, schedule in enumerate(schedules):
            for field in check_fields:
                if schedule.get(field) is None:
                    return Response({'error': '第%s个schedule缺少%s字段' % (i, field)}, status=status.HTTP_400_BAD_REQUEST)
        for schedule in schedules:
            queue_instance.put(schedule)
        return Response({'message': 'put %s schedules to %s' % (len(schedules), queue)})

    @staticmethod
    @api_view(['GET'])
    def status(request):
        return Response({x: y.queue.qsize() for x, y in builtins.schedule_queues.items()})

    @staticmethod
    def get_missing_schedules(request):
        schedule_id = request.GET.get('schedule_id')
        is_strict = request.GET.get('strict', '1') == '1'
        if schedule_id:
            schedules = Schedule.objects.filter(id=schedule_id, status=ScheduleStatus.OPENING.value)
        else:
            schedules = Schedule.objects.filter(is_strict=is_strict, status=ScheduleStatus.OPENING.value)
        missing_result = schedule_util.get_missing_schedules(schedules)
        missing = []
        for pk, target in missing_result.items():
            missing.extend(target)
        return Response(ScheduleSerializer(missing, many=True).data)


class ScheduleProduceView(APIView):

    def post(self, request: Request, pk: int):
        try:
            schedule = Schedule.objects.select_related('task').get(id=pk)
        except Schedule.DoesNotExist:
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


class ClientView(APIView):

    def get(self, request: Request, action: str):
        if action == 'start':
            client = Consumer.objects.create()
            return Response({'client_id': client.id})
        if action == 'register':
            return ClientView.register_client(request)
        client_id = request.GET.get('client_id', '')
        if not client_id.isdigit():
            return Response({'error': 'invalid client_id: %s' % client_id}, status=status.HTTP_400_BAD_REQUEST)
        client: Consumer = Consumer.objects.get(int(client_id))
        if client is None:
            raise NotFound('TaskClient(%s)不存在' % client_id)
        if action == 'stop':
            client.delete()
            return Response({'message': 'stop client(%s) success' % client_id})
        elif action == 'log':
            if client.startup_status == TaskClientStatus.RUNNING.value:
                log = client.runner.read_log()
            else:
                log = client.startup_log
            return HttpResponse(log, content_type='text/plain; charset=utf-8')
        else:
            return Response({'error': 'invalid action: %s, only support start/stop/log' % action},
                            status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    def register_client(request: Request):
        """
        container: Container = None
        group = models.CharField(max_length=100, verbose_name='分组')
        subscription_url = models.CharField(max_length=200, verbose_name='订阅地址')
        subscription_kwargs = models.JSONField(verbose_name='订阅参数', default=dict)
        client_id = models.IntegerField(verbose_name='客户端ID', primary_key=True, default=0)
        process_id = models.PositiveIntegerField(verbose_name='进程ID', null=True, blank=True)
        container_id = models.CharField(max_length=100, verbose_name='容器ID', blank=True, null=True)
        container_name = models.CharField(max_length=100, verbose_name='容器名称', blank=True, null=True)
        container_image = models.CharField(max_length=100, verbose_name='容器镜像', blank=True, null=True)
        container_status = models.CharField(choices=ContainerStatus.choices, default=ContainerStatus.NONE,
                                            max_length=20, verbose_name='容器状态')
        run_in_container = models.BooleanField(default=True, verbose_name='是否在容器中运行')
        env = models.CharField(max_length=500, verbose_name='环境变量', blank=True, null=True)
        startup_status = models.CharField(max_length=500, choices=TaskClientStatus.choices,
                                          verbose_name='启动结果', default=TaskClientStatus.SUCCEED)
        settings = models.TextField(verbose_name='配置', blank=True, null=True)
        create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
        startup_log = models.CharField(max_length=2000, null=True, blank=True)
        """
        data = request.data
        settings = data.get('settings')
        container_id = data.get('container_id')
        subscription_url = data.get('subscription_url')
        subscription_kwargs = data.get('subscription_kwargs')
        process_id = data.get('process_id')
        client = Consumer(container_id=container_id,
                            subscription_url=subscription_url,
                            startup_log='启动成功',
                            settings=settings,
                            process_id=process_id,
                            )
        client.save()
        return Response('上报成功')


def log_view(request: Request, filename):
    page: str = request.GET.get('page', '0')
    page_size = request.GET.get('page_size', '1')
    if page.isdigit() and page_size.isdigit():
        page_size = int(page_size) * 1024
        paged_log = PagedLog(filename, page_size)
        return render(request, 'log_view.html', {
            'paged_log': paged_log,
            'logs': paged_log.read_page(int(page)).split('\n'),
        })
    return Response({'error': f'invalid page({page}) or page_size({page_size})'}, status=status.HTTP_400_BAD_REQUEST)


class ProgramViewMixin:
    agent: ProgramAgent = None

    def get(self, request: Request, action: str):
        agent = self.agent
        agent.state.pull()
        if action == ProgramAction.START:
            error = agent.start()
        elif action == ProgramAction.STOP:
            error = agent.stop()
        elif action == ProgramAction.RESTART:
            error = agent.restart()
        elif action == ProgramAction.LOG:
            return log_view(request, agent.state.log_file)
        else:
            error = 'invalid action: %s, only support start/stop/restart/log' % action
        return Response({"message": error or "OK", "action": action, "state": agent.state},
                        status=status.HTTP_400_BAD_REQUEST if error else status.HTTP_200_OK)


class ProducerView(ProgramViewMixin, APIView):
    agent = producer_agent


class ConsumerView(ProgramViewMixin, APIView):
    agent = consumer_agent


class TaskListView(UserListAPIView):
    queryset = Task.objects.all()
    serializer_class = serializers.TaskSerializer


class TaskDetailView(UserRetrieveAPIView):
    queryset = Task.objects.all()
    serializer_class = serializers.TaskSerializer


class ScheduleListView(UserListAPIView):
    queryset = Schedule.objects.all()
    serializer_class = serializers.ScheduleSerializer


class ScheduleDetailView(RetrieveAPIView):
    queryset = Schedule.objects.all()
    serializer_class = serializers.ScheduleSerializer


class ScheduleLogViewSet(ModelViewSet):
    queryset = ScheduleLog.objects.all()
    serializer_class = serializers.ScheduleLogSerializer


class ExceptionReportView(CreateAPIView):
    queryset = models.ExceptionReport.objects.all()
    serializer_class = serializers.ExceptionSerializer

    def perform_create(self, serializer):
        meta = self.request.META
        ip = meta.get('HTTP_X_FORWARDED_FOR') if meta.get('HTTP_X_FORWARDED_FOR') else meta.get('REMOTE_ADDR')
        serializer.save(ip=ip)


@api_view(['GET'])
def update_settings(request):
    pass
