from . import get_task_model, get_schedule_log_model, get_schedule_model
from . import models
from django_common_objects.serializers import CommonCategorySerializer, CommonTagSerializer
from rest_framework import serializers

TaskModel = get_task_model()
ScheduleModel = get_schedule_model()
ScheduleLogModel = get_schedule_log_model()


class TaskSerializer(serializers.ModelSerializer):
    category = CommonCategorySerializer()
    tags = CommonTagSerializer(many=True)
    parent = serializers.SerializerMethodField()

    def get_parent(self, obj):
        if obj.parent:
            return self.__class__(obj.parent).data

    class Meta:
        exclude = ('update_time', )
        model = TaskModel


class QueueTaskSerializer(TaskSerializer):
    tags = None

    class Meta:
        exclude = ('user', 'update_time', 'description', 'create_time')


class ScheduleCallbackSerializer(serializers.ModelSerializer):

    class Meta:
        exclude = ('update_time', )
        models = models.ScheduleCallback


class ScheduleSerializer(serializers.ModelSerializer):
    task = TaskSerializer()
    callback = ScheduleCallbackSerializer()

    class Meta:
        exclude = ('update_time', )
        model = ScheduleModel


class QueueScheduleSerializer(ScheduleSerializer):
    task = QueueTaskSerializer()
    callback = ScheduleCallbackSerializer()
    schedule_time = serializers.DateTimeField(source="next_schedule_time")
    generator = serializers.SerializerMethodField()
    last_log = serializers.SerializerMethodField()
    queue = serializers.SerializerMethodField()

    @staticmethod
    def get_last_log(obj):
        return getattr(obj, 'last_log', None)

    @staticmethod
    def get_generator(obj):
        return getattr(obj, 'generator', 'auto')

    @staticmethod
    def get_queue(obj):
        return getattr(obj, 'queue')

    class Meta:
        # fields = ('id', 'task', 'schedule_time', 'update_time', 'callback', 'user')
        exclude = ('priority', 'create_time', 'next_schedule_time', 'schedule_start_time',
                   'schedule_end_time', 'status', 'config')


class ScheduleLogSerializer(serializers.ModelSerializer):
    schedule = serializers.PrimaryKeyRelatedField(queryset=ScheduleLogModel.objects.all())

    class Meta:
        fields = '__all__'
        model = ScheduleLogModel


class ExceptionSerializer(serializers.ModelSerializer):
    ip = serializers.ReadOnlyField()

    class Meta:
        fields = '__all__'
        model = models.ExceptionReport
