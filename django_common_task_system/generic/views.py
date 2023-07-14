from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.generics import CreateAPIView
from rest_framework.request import Request
from django.http.response import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from queue import Empty
from datetime import datetime
from django_common_objects.models import CommonCategory
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from jionlp_time import parse_time
from django_common_task_system.utils.schedule_time import nlp_config_to_schedule_config
from django_common_task_system.utils.foreign_key import get_model_related
from .builtins import BaseBuiltinQueues
from .choices import TaskClientStatus
from .client import start_client
from .models import TaskClient
from threading import Thread


UserModel = get_user_model()


def on_system_shutdown(signum, frame):
    print('system shutdown, signal: %s' % signum)
    for client in TaskClient.objects.all():
        client.delete()


@receiver(post_save, sender=TaskClient)
def add_client(sender, instance: TaskClient, created, **kwargs):
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


class TaskScheduleQueueAPI(object):

    def __init__(self, schedule_mode, log_model, queues: BaseBuiltinQueues,
                 serializer, consumer_permissions, permission_validator=None):
        self.schedule_model = schedule_mode
        self.log_model = log_model
        self.queues = queues
        self.serializer = serializer
        self.consumer_permissions = consumer_permissions
        self.permission_validator = permission_validator

    def get(self, request: Request, code: str):
        instance = self.queues.get(code, None)
        if instance is None:
            return JsonResponse({'error': '队列(%s)不存在' % code}, status=status.HTTP_404_NOT_FOUND)
        permission_validator = self.permission_validator or self.consumer_permissions.get(code, None)
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

    def get_by_id(self, request, pk):
        try:
            schedule = self.schedule_model.objects.get(id=pk)
            return Response(self.serializer(schedule).data)
        except self.schedule_model.DoesNotExist:
            return Response({'error': 'schedule not found'}, status=status.HTTP_404_NOT_FOUND)

    @csrf_exempt
    def retry(self, request):
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
            related = get_model_related(self.log_model, excludes=[UserModel, CommonCategory])
            logs = self.log_model.objects.filter(id__in=log_ids).select_related(*related)
            for log in logs:
                schedule = log.schedule
                queue = self.queues[log.queue].queue
                schedule.next_schedule_time = log.schedule_time
                schedule.generator = 'retry'
                schedule.last_log = log.result
                schedule.queue = log.queue
                data = self.serializer(schedule).data
                queue.put(data)
                result[log.id] = log.queue
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'error': '重试失败: %s' % e}, status=status.HTTP_400_BAD_REQUEST)

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
            schedules = self.schedule_model.objects.filter(id__in=set(schedule_ids))
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
                data = self.serializer(schedule).data
                queue_instance.queue.put(data)
                schedule_result.append(t.strftime('%Y-%m-%d %H:%M:%S'))
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'error': '添加到队列失败: %s' % e}, status=status.HTTP_400_BAD_REQUEST)

    def status(self, request):
        return JsonResponse({x: y.queue.qsize() for x, y in self.queues.items()})


class ExceptionReportView(CreateAPIView):

    def perform_create(self, serializer):
        meta = self.request.META
        group = self.request.POST.get('group')
        if not group:
            url_name = self.request.stream.resolver_match.url_name
            if url_name == 'user-exception-report':
                group = 'user'
            elif url_name == 'system-exception-report':
                group = 'system'
            else:
                group = url_name
        ip = meta.get('HTTP_X_FORWARDED_FOR') if meta.get('HTTP_X_FORWARDED_FOR') else meta.get('REMOTE_ADDR')
        serializer.save(ip=ip, group=group)


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
