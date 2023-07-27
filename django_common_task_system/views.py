from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from rest_framework.viewsets import ModelViewSet
from . import serializers, get_user_task_model, get_schedule_log_model, get_user_schedule_model, get_user_schedule_serializer
from . import models
from django_common_objects.rest_view import UserListAPIView, UserRetrieveAPIView
from django_common_task_system.generic import views as generic_views, system_initialize_signal
from django_common_task_system.generic import schedule_backend
from .builtins import builtins


UserTaskModel = get_user_task_model()
UserScheduleLogModel = get_schedule_log_model()
UserScheduleModel = get_user_schedule_model()
ScheduleSerializer = get_user_schedule_serializer()


@receiver(system_initialize_signal, sender='system_initialized')
def on_system_initialized(sender, **kwargs):
    thread = schedule_backend.TaskScheduleThread(
        schedule_model=UserScheduleModel,
        builtins=builtins,
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


@receiver(post_save, sender=models.ScheduleConsumerPermission)
def add_consumer_permission(sender, instance: models.ScheduleConsumerPermission, created, **kwargs):
    builtins.consumer_permissions.add(instance)


@receiver(post_delete, sender=models.ScheduleConsumerPermission)
def delete_consumer_permission(sender, instance: models.ScheduleConsumerPermission, **kwargs):
    builtins.consumer_permissions.delete(instance)


class TaskListView(UserListAPIView):
    queryset = UserTaskModel.objects.all()
    serializer_class = serializers.TaskSerializer


class TaskDetailView(UserRetrieveAPIView):
    queryset = UserTaskModel.objects.all()
    serializer_class = serializers.TaskSerializer


class TaskScheduleListView(UserListAPIView):
    queryset = UserScheduleModel.objects.all()
    serializer_class = serializers.TaskScheduleSerializer


class TaskScheduleDetailView(UserRetrieveAPIView):
    queryset = UserScheduleModel.objects.all()
    serializer_class = serializers.TaskScheduleSerializer


class ScheduleLogViewSet(ModelViewSet):
    queryset = UserScheduleLogModel.objects.all()
    serializer_class = serializers.TaskScheduleLogSerializer


class ExceptionReportView(generic_views.ExceptionReportView):
    queryset = models.ExceptionReport.objects.all()
    serializer_class = serializers.ExceptionSerializer


TaskScheduleQueueAPI = generic_views.TaskScheduleQueueAPI(
    schedule_mode=UserScheduleModel, log_model=UserScheduleLogModel,
    queues=builtins.queues, serializer=ScheduleSerializer,
    consumer_permissions=builtins.consumer_permissions,
)
