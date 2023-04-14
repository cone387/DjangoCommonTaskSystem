from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from django.http.response import JsonResponse
from . import serializers, get_task_model, get_schedule_log_model, get_task_schedule_model
from .models import TaskSchedule, TaskScheduleProducer, TaskScheduleQueue, builtins
from django_common_objects.rest_view import UserListAPIView, UserRetrieveAPIView
from queue import Empty
from datetime import datetime
from jionlp_time import parse_time
from .utils.schedule_time import nlp_config_to_schedule_config
from threading import Thread
import os
import time


TaskModel = get_task_model()
ScheduleLogModel = get_schedule_log_model()
ScheduleModel = get_task_schedule_model()


class TaskScheduleThread(Thread):
    schedule_model = ScheduleModel
    producer = TaskScheduleProducer
    serializer = serializers.QueueScheduleSerializer
    queues = builtins.queues

    def __init__(self):
        super().__init__(daemon=True)

    def produce(self):
        for producer in self.producer.objects.filter(status=True):
            queue = self.queues[producer.queue.code]
            queryset = self.schedule_model.objects.filter(**producer.filters)
            if producer.lte_now:
                queryset = queryset.filter(next_schedule_time__lte=datetime.now())
            for schedule in queryset:
                data = self.serializer(schedule).data
                data['queue'] = queue.code
                queue.queue.put(data)
                schedule.generate_next_schedule()

    def run(self) -> None:
        while True:
            try:
                self.produce()
            except Exception as err:
                print(err)
            time.sleep(0.5)


if os.environ.get('RUN_MAIN') == 'true' and os.environ.get('RUN_CLIENT') != 'true':
    from django.conf import settings
    if 'django_common_task_system' in settings.INSTALLED_APPS:
        builtins.initialize()
        thread = TaskScheduleThread()
        thread.start()


@receiver(post_delete, sender=TaskScheduleQueue)
def delete_queue(sender, instance: TaskScheduleQueue, **kwargs):
    builtins.queues.delete(instance)


@receiver(post_save, sender=TaskScheduleQueue)
def add_queue(sender, instance: TaskScheduleQueue, created, **kwargs):
    builtins.queues.add(instance)


class TaskListView(UserListAPIView):
    queryset = TaskModel.objects.all()
    serializer_class = serializers.TaskSerializer


class TaskDetailView(UserRetrieveAPIView):
    queryset = TaskModel.objects.all()
    serializer_class = serializers.TaskSerializer


class TaskScheduleListView(UserListAPIView):
    queryset = TaskSchedule.objects.all()
    serializer_class = serializers.TaskScheduleSerializer


class TaskScheduleDetailView(UserRetrieveAPIView):
    queryset = TaskSchedule.objects.all()
    serializer_class = serializers.TaskScheduleSerializer


class ScheduleLogViewSet(ModelViewSet):
    queryset = ScheduleLogModel.objects.all()
    serializer_class = serializers.TaskScheduleLogSerializer


class TaskScheduleQueueAPI(object):
    queues = builtins.queues
    schedule_model = TaskSchedule
    log_model = ScheduleLogModel

    @classmethod
    def get(cls, request: Request, code: str):
        instance = cls.queues.get(code, None)
        if instance is None:
            return JsonResponse({'message': '队列(%s)不存在' % code}, status=status.HTTP_404_NOT_FOUND)
        try:
            task = instance.queue.get_nowait()
        except Empty:
            return JsonResponse({'message': 'no schedule for %s' % code}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return JsonResponse({'message': 'get schedule error: %s' % e}, status=status.HTTP_400_BAD_REQUEST)
        return JsonResponse(task)

    @classmethod
    def get_by_id(cls, request, pk):
        try:
            schedule = cls.schedule_model.objects.get(id=pk)
            return Response(serializers.QueueScheduleSerializer(schedule).data)
        except TaskSchedule.DoesNotExist:
            return Response({'msg': 'schedule not found'}, status=status.HTTP_404_NOT_FOUND)

    @classmethod
    def retry(cls, request):
        log_ids = request.GET.get('log-ids', None)
        if not log_ids:
            return JsonResponse({'error': 'log-ids不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            log_ids = [int(i) for i in log_ids.split(',')]
            assert len(log_ids) < 1000, 'log-ids不能超过1000个'
        except Exception as e:
            return JsonResponse({'error': 'logs_ids参数错误: %s' % e}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = {x: 'no such log' for x in log_ids}
            logs = cls.log_model.objects.filter(id__in=log_ids)
            for log in logs:
                queue = cls.queues[log.queue].queue
                log.schedule.next_schedule_time = log.schedule_time
                data = serializers.QueueScheduleSerializer(log.schedule).data
                data['queue'] = log.queue
                queue.put(data)
                result[log.id] = log.queue
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'error': '重试失败: %s' % e}, status=status.HTTP_400_BAD_REQUEST)

    @classmethod
    def put(cls, request: Request):
        schedule_ids = request.GET.get('i', None)
        queues = request.GET.get('q', None)
        schedule_times = request.GET.get('t', None)
        if not schedule_ids or not queues or not schedule_times:
            return JsonResponse({'error': 'schedule_ids(i)、queues(q)、schedule_times(t)不能为空'},
                                status=status.HTTP_400_BAD_REQUEST)
        try:
            schedule_ids = [int(i) for i in schedule_ids.split(',')]
            queues = [i.strip() for i in queues.split(',')]
            schedule_times = [datetime.strptime(i, '%Y-%m-%d %H:%M:%S') for i in schedule_times.split(',')]
            assert len(schedule_ids) < 1000, '不能超过1000个'
            if len(queues) == 1:
                queue_mapping = {x: queues[0] for x in schedule_ids}
            elif len(queues) == len(schedule_ids):
                queue_mapping = dict(zip(schedule_ids, queues))
            else:
                raise Exception('ids和queues长度不一致')
            if len(schedule_times) == 1:
                schedule_time_mapping = {x: schedule_times[0] for x in schedule_ids}
            elif len(schedule_times) == len(schedule_ids):
                schedule_time_mapping = dict(zip(schedule_ids, schedule_times))
            else:
                raise Exception('ids和schedule_times长度不一致')
        except Exception as e:
            return JsonResponse({'error': 'ids参数错误: %s' % e}, status=status.HTTP_400_BAD_REQUEST)
        try:
            schedules = cls.schedule_model.objects.filter(id__in=schedule_ids)
            result = {x: 'no such schedule' for x in schedule_ids}
            for schedule in schedules:
                queue = cls.queues.get(queue_mapping[schedule.id], None)
                if queue is None:
                    result[schedule.id] = 'no such queue: %s' % queue_mapping[schedule.id]
                else:
                    schedule.next_schedule_time = schedule_time_mapping[schedule.id]
                    data = serializers.QueueScheduleSerializer(schedule).data
                    data['queue'] = queue_mapping[schedule.id]
                    queue.queue.put(data)
                    result[schedule.id] = queue_mapping[schedule.id]
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'error': '添加到队列失败: %s' % e}, status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    @api_view(['GET'])
    def status(request):
        return Response({x: y.queue.qsize() for x, y in builtins.queues.items()})


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
