from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from . import serializers, get_task_model, get_schedule_log_model, get_task_schedule_model, get_task_schedule_serializer
from .models import TaskSchedule, TaskScheduleProducer, TaskScheduleQueue, \
    ConsumerPermission, ExceptionReport
from django_common_objects.rest_view import UserListAPIView, UserRetrieveAPIView
from django_common_task_system.generic import views as generic_views, system_initialize_signal
from django_common_task_system.generic import schedule_backend
from jionlp_time import parse_time
from .utils.schedule_time import nlp_config_to_schedule_config
from .builtins import builtins


TaskModel = get_task_model()
ScheduleLogModel = get_schedule_log_model()
ScheduleModel = get_task_schedule_model()
ScheduleSerializer = get_task_schedule_serializer()


@receiver(system_initialize_signal, sender='system_initialized')
def on_system_initialized(sender, **kwargs):
    thread = schedule_backend.TaskScheduleThread(
        schedule_model=ScheduleModel,
        builtins=builtins,
        schedule_serializer=ScheduleSerializer
    )
    thread.start()


@receiver(post_delete, sender=TaskScheduleQueue)
def delete_queue(sender, instance: TaskScheduleQueue, **kwargs):
    builtins.queues.delete(instance)


@receiver(post_save, sender=TaskScheduleQueue)
def add_queue(sender, instance: TaskScheduleQueue, created, **kwargs):
    builtins.queues.add(instance)


@receiver(post_save, sender=TaskScheduleProducer)
def add_producer(sender, instance: TaskScheduleProducer, created, **kwargs):
    builtins.producers.add(instance)


@receiver(post_delete, sender=TaskScheduleProducer)
def delete_producer(sender, instance: TaskScheduleProducer, **kwargs):
    builtins.producers.delete(instance)


@receiver(post_save, sender=ConsumerPermission)
def add_consumer_permission(sender, instance: ConsumerPermission, created, **kwargs):
    builtins.consumer_permissions.add(instance)


@receiver(post_delete, sender=ConsumerPermission)
def delete_consumer_permission(sender, instance: ConsumerPermission, **kwargs):
    builtins.consumer_permissions.delete(instance)


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


class ExceptionReportView(generic_views.ExceptionReportView):
    queryset = ExceptionReport.objects.all()
    serializer_class = serializers.ExceptionSerializer


TaskScheduleQueueAPI = generic_views.TaskScheduleQueueAPI(
    schedule_mode=ScheduleModel, log_model=ScheduleLogModel,
    queues=builtins.queues, serializer=ScheduleSerializer,
    consumer_permissions=builtins.consumer_permissions,
)
