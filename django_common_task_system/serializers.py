from . import models
from django_common_objects.serializers import CommonCategorySerializer, CommonTagSerializer
from rest_framework import serializers
from . import get_task_model, get_schedule_log_model


TaskModel = get_task_model()
TaskScheduleLogModel = get_schedule_log_model()


class TaskSerializer(serializers.ModelSerializer):
    category = CommonCategorySerializer()
    tags = CommonTagSerializer(many=True)
    parent = serializers.SerializerMethodField()

    def get_parent(self, obj):
        if obj.parent:
            return self.__class__(obj.parent).data

    class Meta:
        model = TaskModel
        exclude = ('update_time', )


class QueueTaskSerializer(TaskSerializer):
    tags = None

    class Meta:
        model = TaskModel
        # fields = ('id', 'name', 'config', 'category', 'status', 'parent', )
        exclude = ('user', 'update_time', 'description', 'create_time')


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
    schedule_time = serializers.DateTimeField(source="next_schedule_time")

    class Meta:
        model = models.TaskSchedule
        # fields = ('id', 'task', 'schedule_time', 'update_time', 'callback', 'user')
        exclude = ('priority', 'create_time', 'next_schedule_time', 'schedule_start_time',
                   'schedule_end_time', 'status', 'config')


class TaskScheduleLogSerializer(serializers.ModelSerializer):
    schedule = serializers.PrimaryKeyRelatedField(queryset=models.TaskSchedule.objects.all())

    class Meta:
        model = TaskScheduleLogModel
        fields = '__all__'


class ExceptionSerializer(serializers.ModelSerializer):
    ip = serializers.ReadOnlyField()

    class Meta:
        model = models.ExceptionReport
        fields = '__all__'
