from datetime import datetime
from queue import Empty
from threading import Thread
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
from .choices import TaskClientStatus, ScheduleStatus
from .client import start_client
from .models import TaskClient
from .builtins import builtins
from . import serializers, get_task_model, get_schedule_log_model, get_schedule_model, get_schedule_serializer
from . import models, system_initialized_signal, schedule_backend


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
    def put(self, request: Request):
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
                queue_instance = self.queues.get(q, None)
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

        schedule_start_time = request.GET.get('start_time', None)
        schedule_end_date = request.GET.get('end_time', None)
        result = {}
        errors = {'producer_not_found': [], 'schedule_time_diff': [], 'schedule_interval': []}
        producer_not_found_errors = errors['producer_not_found']
        schedule_time_diff_errors = errors['schedule_time_diff']
        schedule_interval_errors = errors['schedule_interval']

        for schedule in schedules:
            schedule.config['base_on_now'] = False
            schedule_times = get_schedule_times(schedule, start_date=schedule_start_time, end_date=schedule_end_date)
            diffs = set()
            if len(schedule_times) < 2:
                info = "%s schedule times is less than 2, ignored" % schedule
                result[schedule.id] = info
                continue
            for i in range(len(schedule_times) - 1):
                a = schedule_times[i]
                b = schedule_times[i + 1]
                diff = b - a
                seconds = int(diff.total_seconds())
                diffs.add(seconds)
            if len(diffs) != 1:
                schedule_time_diff_errors.append(diffs)
                continue
            diff = diffs.pop()
            if diff % (3600 * 24) == 0:
                dimension = 'DAY'
                interval = diff // (3600 * 24)
            elif diff % 3600 == 0:
                dimension = 'HOUR'
                interval = diff // 3600
            elif diff % 60 == 0:
                dimension = 'MINUTE'
                interval = diff // 60
            else:
                schedule_interval_errors.append("%s: %s" % (strict_schedule.id, diff))
                continue
            max_failed_times = self.schedule.task.config.get('max_failed_times', 3)
            start_date, end_date = schedule_times[0], schedule_times[-1]
            lens = len(schedule_times)
            # 这里batch=700是因为mysql.help_topic表的最大id是699，也就是700条数据
            batch = 700
            schedule_date_commands = []
            for i, x in enumerate(range(0, lens, batch)):
                b = x + batch - 1 if x + batch - 1 < lens else lens - 1
                st, et = schedule_times[x], schedule_times[b]
                schedule_date_commands.append(f"""
                            SELECT
                            date_add('{st}', INTERVAL + t{i}.help_topic_id * {interval} {dimension} ) AS date 
                        FROM
                            mysql.help_topic t{i} 
                        WHERE
                            t{i}.help_topic_id <= timestampdiff({dimension}, '{st}', '{et}') 
                        """)
            schedule_date_command = ' union all '.join(schedule_date_commands)
            command = f"""
                        select a.date from ({schedule_date_command}) a 
                        left join (
                            select schedule_time, count(status != 'F' or null) as succeed, 
                                count(status='F' or null) as failed from {schedule_log_model._meta.db_table} where 
                                schedule_id = {strict_schedule.id} and 
                                schedule_time between '{start_date}' and '{end_date}'
                                group by schedule_time
                        ) b 
                        on a.date = b.schedule_time where b.succeed is null or (b.succeed = 0 and b.failed < {max_failed_times})
                    """
            missing_datetimes = []
            time = strict_schedule.config[strict_schedule.config['schedule_type']].get('time', '03:00:00')
            with connection.cursor() as cursor:
                cursor.execute(command)
                for d, *_ in cursor.fetchall():
                    # 根据日志查出来的遗漏日期就是实际的日期，不需要根据latest_days来计算
                    if len(d) == 10:
                        d = d + ' ' + time
                    missing_datetimes.append(d)
            if missing_datetimes:
                logger.info("%s missing times: %s" % (strict_schedule, len(missing_datetimes)))
                url = urljoin(settings.HOST, reverse(handle_url_name))
                result[strict_schedule.id] = put_schedule(url, strict_schedule, queue, missing_datetimes)
            else:
                logger.info("%s no missing times" % strict_schedule)
        for k, v in errors.items():
            if v:
                break
        else:
            # no error
            if not result:
                raise EmptyResult("no strict schedule need to be executed")
            return result
        result['errors'] = errors
        raise ValueError(result)


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
        client = TaskClient.objects.get(client_id=client_id)
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
