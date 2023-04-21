from django_common_task_system import serializers
from rest_framework.serializers import PrimaryKeyRelatedField
from . import models


class TaskSerializer(serializers.TaskSerializer):

    class Meta(serializers.TaskSerializer.Meta):
        model = models.SystemTask


class QueueTaskSerializer(serializers.QueueTaskSerializer):

    class Meta(serializers.QueueTaskSerializer.Meta):
        model = models.SystemTask


class TaskCallbackSerializer(serializers.TaskCallbackSerializer):

    class Meta(serializers.TaskCallbackSerializer.Meta):
        model = models.SystemScheduleCallback


class TaskScheduleSerializer(serializers.TaskScheduleSerializer):
    task = TaskSerializer()
    callback = TaskCallbackSerializer()

    class Meta(serializers.TaskScheduleSerializer.Meta):
        model = models.SystemSchedule


class QueueScheduleSerializer(serializers.QueueScheduleSerializer):
    task = QueueTaskSerializer()
    callback = TaskCallbackSerializer()

    class Meta(serializers.QueueScheduleSerializer.Meta):
        model = models.SystemSchedule
        exclude = ('priority', 'create_time', 'next_schedule_time', 'schedule_start_time',
                   'schedule_end_time', 'status')


class TaskScheduleLogSerializer(serializers.TaskScheduleLogSerializer):
    schedule = PrimaryKeyRelatedField(queryset=models.SystemSchedule.objects.all())

    class Meta(serializers.TaskScheduleLogSerializer.Meta):
        model = models.SystemScheduleLog


class ExceptionSerializer(serializers.ExceptionSerializer):

    class Meta(serializers.ExceptionSerializer.Meta):
        model = models.SystemExceptionReport
