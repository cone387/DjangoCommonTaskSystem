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

    class Meta(TaskSerializer.Meta):
        exclude = ('user', 'update_time', 'description', 'create_time')


class ScheduleCallbackSerializer(serializers.ModelSerializer):

    class Meta:
        exclude = ('update_time', )
        model = models.ScheduleCallback


class ScheduleSerializer(serializers.ModelSerializer):
    task = TaskSerializer()
    callback = ScheduleCallbackSerializer()
    schedule_time = serializers.DateTimeField(source="next_schedule_time")

    class Meta:
        exclude = ('update_time', )
        model = ScheduleModel


class QueueScheduleSerializer(ScheduleSerializer):
    task = QueueTaskSerializer()
    callback = ScheduleCallbackSerializer()
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
        return getattr(obj, 'queue', None)

    class Meta(ScheduleSerializer.Meta):
        # fields = ('id', 'task', 'schedule_time', 'update_time', 'callback', 'user')
        exclude = ('priority', 'create_time', 'next_schedule_time', 'schedule_start_time',
                   'schedule_end_time', 'status', 'config')


class ScheduleLogSerializer(serializers.ModelSerializer):
    schedule = serializers.PrimaryKeyRelatedField(queryset=ScheduleModel.objects.all())

    class Meta:
        fields = '__all__'
        model = ScheduleLogModel


class ExceptionSerializer(serializers.ModelSerializer):
    ip = serializers.ReadOnlyField()

    class Meta:
        fields = '__all__'
        model = models.ExceptionReport


# class MachineSerializer(serializers.ModelSerializer):
#     internet_ip = serializers.IPAddressField(required=False, allow_blank=True, allow_null=True)
#     mac = serializers.CharField(required=False, label='MAC地址', max_length=12)
#
#     class Meta:
#         fields = '__all__'
#         model = models.Machine
#         validators = []


class ConsumerSerializer(serializers.ModelSerializer):
    id = serializers.CharField(max_length=36)

    def validate_machine(self, machine):
        if not isinstance(machine, dict):
            raise serializers.ValidationError('machine must be a dict')
        meta = self.context['request'].META
        internet_ip = meta.get('HTTP_X_FORWARDED_FOR', meta.get('REMOTE_ADDR', None))
        machine['internet_ip'] = internet_ip
        try:
            models.Machine(**machine)
        except Exception as e:
            raise serializers.ValidationError(e)
        return machine

    @staticmethod
    def validate_container(container):
        if not container:
            return {}
        if not isinstance(container, dict):
            raise serializers.ValidationError('container must be a dict')
        data = {}
        for filed in models.Container._fields:
            if container.get(filed) is None:
                raise serializers.ValidationError(f'{filed} is required')
            data[filed] = container[filed]
        return data

    class Meta:
        fields = '__all__'
        model = models.Consumer
        validators = []
