from rest_framework import serializers
from . import get_task_model, get_schedule_log_model, get_task_schedule_model
from . import models
from django_common_task_system.generic import serializers as generic_serializers


TaskModel = get_task_model()
ScheduleModel = get_task_schedule_model()
TaskScheduleLogModel = get_schedule_log_model()


class TaskSerializer(generic_serializers.TaskSerializer):

    class Meta(generic_serializers.TaskSerializer.Meta):
        model = TaskModel


class QueueTaskSerializer(generic_serializers.QueueTaskSerializer):

    class Meta(generic_serializers.QueueTaskSerializer.Meta):
        model = TaskModel


class TaskCallbackSerializer(generic_serializers.TaskCallbackSerializer):

    class Meta(generic_serializers.TaskCallbackSerializer.Meta):
        model = models.TaskScheduleCallback


class TaskScheduleSerializer(generic_serializers.TaskScheduleSerializer):
    task = TaskSerializer()
    callback = TaskCallbackSerializer()

    class Meta(generic_serializers.TaskScheduleSerializer.Meta):
        model = ScheduleModel


class QueueScheduleSerializer(generic_serializers.QueueScheduleSerializer):
    task = QueueTaskSerializer()
    callback = TaskCallbackSerializer()

    class Meta(generic_serializers.QueueScheduleSerializer.Meta):
        model = ScheduleModel


class TaskScheduleLogSerializer(generic_serializers.TaskScheduleLogSerializer):
    schedule = serializers.PrimaryKeyRelatedField(queryset=ScheduleModel.objects.all())

    class Meta(generic_serializers.TaskScheduleLogSerializer.Meta):
        model = TaskScheduleLogModel


class ExceptionSerializer(generic_serializers.ExceptionSerializer):

    class Meta(generic_serializers.ExceptionSerializer.Meta):
        model = models.ExceptionReport
