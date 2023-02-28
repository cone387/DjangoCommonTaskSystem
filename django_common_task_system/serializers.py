from . import models
from django_common_objects.serializers import CommonCategorySerializer, CommonTagSerializer
from rest_framework import serializers


class TaskSerializer(serializers.ModelSerializer):
    category = CommonCategorySerializer()
    tags = CommonTagSerializer(many=True)
    parent = serializers.SerializerMethodField()

    def get_parent(self, obj):
        if obj.parent:
            return self.__class__(obj.parent).data

    class Meta:
        model = models.Task
        exclude = ('update_time', )


class QueueTaskSerializer(TaskSerializer):

    class Meta:
        model = models.Task
        fields = ('id', 'name', 'config', 'category', 'status', 'parent', )


class TaskCallbackSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.TaskScheduleCallback
        exclude = ('update_time', )


class TaskScheduleSerializer(serializers.ModelSerializer):
    task = TaskSerializer()
    callback = TaskCallbackSerializer()

    class Meta:
        model = models.TaskSchedule
        exclude = ('update_time', )


class QueueScheduleSerializer(TaskScheduleSerializer):
    task = QueueTaskSerializer()
    callback = TaskCallbackSerializer()

    class Meta:
        model = models.TaskSchedule
        fields = ('id', 'task', 'type', 'next_schedule_time', 'update_time', 'callback', 'user')


class TaskScheduleLogSerializer(serializers.ModelSerializer):
    schedule = TaskScheduleSerializer()

    class Meta:
        model = models.TaskScheduleLog
        exclude = ('update_time', )
