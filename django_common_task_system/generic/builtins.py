import os
from collections import OrderedDict
from django.db.utils import ProgrammingError, OperationalError
from django.dispatch import receiver
from django.utils.module_loading import import_string
from django_common_task_system.generic.choices import TaskScheduleStatus
from django_common_task_system.generic.models import (
    AbstractTaskScheduleQueue, AbstractTaskScheduleProducer, AbstractConsumerPermission)
from django_common_task_system.permissions import ConsumerPermissionValidator
from django.conf import settings

from . import App
from .signal import system_initialize_signal
from django.contrib.auth import get_user_model


UserModel = get_user_model()


class BuiltinModels(OrderedDict):
    model = None
    model_unique_kwargs = []

    def init_object(self, obj):
        kwargs = {
            key: getattr(obj, key) for key in self.model_unique_kwargs
        }
        defaults = {
            filed.name: getattr(obj, filed.name) for filed in obj._meta.fields if filed.name not in kwargs
        }
        current = self.model.objects.get_or_create(
            defaults=defaults, **kwargs
        )[0]
        for field in obj._meta.fields:
            setattr(obj, field.name, getattr(current, field.name))
        return obj

    def initialize(self):
        for k, v in self.__dict__.items():
            if isinstance(v, self.model):
                obj = self.init_object(v)
                self.add(obj, k)

    def add(self, obj, key=None):
        if key:
            self[key] = obj

    def delete(self, obj, key):
        if key:
            self.pop(key, None)


class BaseBuiltinQueues(BuiltinModels):
    status_params_mapping = {
        TaskScheduleStatus.OPENING.value: 'opening',
        TaskScheduleStatus.CLOSED.value: 'closed',
        TaskScheduleStatus.TEST.value: 'test',
        TaskScheduleStatus.DONE.value: 'done',
        TaskScheduleStatus.ERROR.value: 'error',
    }

    model_unique_kwargs = ['code']

    def __init__(self):
        super(BaseBuiltinQueues, self).__init__()
        try:
            for m in self.model.objects.filter(status=True):
                self.add(m)
        except (ProgrammingError, OperationalError):
            pass

    def add(self, instance: AbstractTaskScheduleQueue, key=None):
        if instance.status:
            old = self.get(instance.code)
            if not old or old.module != instance.module or old.config != instance.config:
                instance.queue = import_string(instance.module)(**instance.config)
                self[instance.code] = instance
        elif not instance.status:
            self.pop(instance.code, None)

    def delete(self, instance: AbstractTaskScheduleQueue, key=None):
        self.pop(instance.code, None)


class BaseBuiltinProducers(BuiltinModels):
    model_unique_kwargs = ['queue']

    def __init__(self):
        super(BaseBuiltinProducers, self).__init__()
        try:
            for m in self.model.objects.filter(status=True):
                self.add(m)
        except (ProgrammingError, OperationalError):
            pass

    def add(self, instance: AbstractTaskScheduleProducer, key=None):
        if instance.status:
            old = self.get(instance.id)
            if not old or old.queue != instance.queue:
                self[instance.id] = instance
        elif not instance.status:
            self.pop(instance.id, None)

    def delete(self, instance: AbstractTaskScheduleProducer, key=None):
        self.pop(instance.id, None)


class BaseConsumerPermissions(BuiltinModels):
    model = AbstractConsumerPermission
    model_unique_kwargs = ['producer', 'type']

    def __init__(self):
        super(BaseConsumerPermissions, self).__init__()
        try:
            for m in self.model.objects.filter(status=True):
                self.add(m)
        except (ProgrammingError, OperationalError):
            pass

    def add(self, instance: AbstractConsumerPermission, key=None):
        if instance.status:
            old = self.get(instance.producer_id)
            if not old or old.type != instance.type or old.config != instance.config:
                validator = ConsumerPermissionValidator.get(instance.type)
                if validator:
                    self[instance.producer.queue.code] = validator(instance.config)
        elif not instance.status:
            self.pop(instance.producer.queue.code, None)

    def delete(self, instance: AbstractConsumerPermission, key=None):
        self.pop(instance.producer.queue.code, None)


class BaseBuiltins:
    app = None

    def __init__(self):
        self._initialized = False
        self.user = UserModel(username='系统', is_superuser=True)

    def init_user(self):
        user = UserModel.objects.filter(is_superuser=True).order_by('id').first()
        if not user:
            raise Exception('请先创建超级用户')
        for field in user._meta.fields:
            setattr(self.user, field.name, getattr(user, field.name))

    @classmethod
    def is_app_installed(cls, app=None):
        return (app or cls.app) in settings.INSTALLED_APPS

    def initialize(self):
        if not self._initialized:
            self._initialized = True
            if os.environ.get('RUN_MAIN') == 'true' and os.environ.get('RUN_CLIENT') != 'true':
                if self.is_app_installed:
                    print('[%s]初始化内置任务' % self.app)
                    self.init_user()
                    for i in self.__dict__.values():
                        if isinstance(i, BuiltinModels):
                            i.initialize()
                    system_initialize_signal.send(sender='builtin_initialized', app=self.app)


is_task_initialized = App.user_task in settings.INSTALLED_APPS
is_system_task_initialized = App.system_task in settings.INSTALLED_APPS
is_system_signal_sent = False


@receiver(system_initialize_signal, sender='builtin_initialized')
def on_builtin_initialized(sender, app=None, **kwargs):
    global is_task_initialized, is_system_task_initialized, is_system_signal_sent
    if app == 'django_common_task_system':
        is_task_initialized = True
    elif app == 'django_common_task_system.system_task':
        is_system_task_initialized = True
    # 加入system_signal_sent判断, 防止重复发送信号
    if is_task_initialized and is_system_task_initialized and not is_system_signal_sent:
        from threading import Timer

        def send_signal():
            system_initialize_signal.send(sender='system_initialized')
        # 这里django_common_task_system和django_common_system_task都初始化完成了, 但是其他app还未
        # 完成初始化, 所以这里延迟一段时间再发送信号
        is_system_signal_sent = True
        Timer(2, send_signal).start()
