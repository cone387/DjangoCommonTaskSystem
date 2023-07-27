from rest_framework import serializers
from . import get_user_task_model, get_schedule_log_model, get_user_schedule_model
from . import models
from django_common_task_system.generic import serializers as generic_serializers


UserTaskModel = get_user_task_model()
UserScheduleModel = get_user_schedule_model()
UserScheduleLogModel = get_schedule_log_model()


class TaskSerializer(generic_serializers.TaskSerializer):

    class Meta(generic_serializers.TaskSerializer.Meta):
        model = UserTaskModel


class QueueTaskSerializer(generic_serializers.QueueTaskSerializer):

    class Meta(generic_serializers.QueueTaskSerializer.Meta):
        model = UserTaskModel


class TaskCallbackSerializer(generic_serializers.TaskCallbackSerializer):

    class Meta(generic_serializers.TaskCallbackSerializer.Meta):
        model = models.ScheduleCallback


class TaskScheduleSerializer(generic_serializers.TaskScheduleSerializer):
    task = TaskSerializer()
    callback = TaskCallbackSerializer()

    class Meta(generic_serializers.TaskScheduleSerializer.Meta):
        model = UserScheduleModel


class QueueScheduleSerializer(generic_serializers.QueueScheduleSerializer):
    task = QueueTaskSerializer()
    callback = TaskCallbackSerializer()

    class Meta(generic_serializers.QueueScheduleSerializer.Meta):
        model = UserScheduleModel


class TaskScheduleLogSerializer(generic_serializers.TaskScheduleLogSerializer):
    schedule = serializers.PrimaryKeyRelatedField(queryset=UserScheduleModel.objects.all())

    class Meta(generic_serializers.TaskScheduleLogSerializer.Meta):
        model = UserScheduleLogModel


class ExceptionSerializer(generic_serializers.ExceptionSerializer):

    class Meta(generic_serializers.ExceptionSerializer.Meta):
        model = models.ExceptionReport
