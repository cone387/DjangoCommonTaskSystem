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
        exclude = ('update_time', )


class QueueTaskSerializer(TaskSerializer):
    tags = None

    class Meta:
        exclude = ('user', 'update_time', 'description', 'create_time')


class TaskCallbackSerializer(serializers.ModelSerializer):

    class Meta:
        exclude = ('update_time', )


class TaskScheduleSerializer(serializers.ModelSerializer):
    task = TaskSerializer()
    callback = TaskCallbackSerializer()

    class Meta:
        exclude = ('update_time', )


class QueueScheduleSerializer(TaskScheduleSerializer):
    task = QueueTaskSerializer()
    callback = TaskCallbackSerializer()
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


class TaskScheduleLogSerializer(serializers.ModelSerializer):
    # schedule = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        fields = '__all__'


class ExceptionSerializer(serializers.ModelSerializer):
    ip = serializers.ReadOnlyField()

    class Meta:
        fields = '__all__'
