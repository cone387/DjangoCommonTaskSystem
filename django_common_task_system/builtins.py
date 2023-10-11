import os
from collections import OrderedDict
from django.db import ProgrammingError, OperationalError
from django.utils.module_loading import import_string
from django_common_objects.models import CommonCategory
from django_common_task_system.choices import (
    ScheduleCallbackEvent, ScheduleCallbackStatus, ScheduleStatus, ScheduleQueueModule
)
from django_common_task_system.models import (
    ScheduleCallback, ScheduleQueuePermission, ScheduleQueue, ScheduleProducer, UserModel, Schedule
)
from django_common_task_system.permissions import ConsumerPermissionValidator
from . import get_task_model, get_schedule_model, get_schedule_log_model, system_initialized_signal

TaskModel = get_task_model()
ScheduleModel: Schedule = get_schedule_model()
ScheduleLogModel = get_schedule_log_model()


DEFAULT_USER = UserModel(username='系统', is_superuser=True)


class BuiltinModels(OrderedDict):
    model = None
    model_unique_kwargs = []

    def init_object(self, obj):
        obj.user = DEFAULT_USER
        kwargs = {
            key: getattr(obj, key) for key in self.model_unique_kwargs
        }
        defaults = {}
        for field in obj._meta.fields:
            if field.name not in kwargs:
                defaults[field.name] = getattr(obj, field.name)
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


class Categories(BuiltinModels):
    model = CommonCategory
    model_unique_kwargs = ('name',)

    def __init__(self):
        model = TaskModel._meta.label
        self.system_task = self.model(
            name='系统任务',
            model=model,
        )

        self.system_base = self.model(
            name='系统基础',
            model=model,
        )

        self.system_test = self.model(
            name='系统测试',
            model=model,
        )
        super(Categories, self).__init__()


class ScheduleQueues(BuiltinModels):
    status_params_mapping = {
        ScheduleStatus.OPENING.value: 'opening',
        ScheduleStatus.CLOSED.value: 'closed',
        ScheduleStatus.TEST.value: 'test',
        ScheduleStatus.DONE.value: 'done',
        ScheduleStatus.ERROR.value: 'error',
    }

    model_unique_kwargs = ['code']
    model = ScheduleQueue

    def __init__(self):
        self.opening = self.model(
            code=self.status_params_mapping[ScheduleStatus.OPENING.value],
            status=True,
            module=ScheduleQueueModule.DEFAULT,
            name='已启用任务',
        )
        self.system = self.model(
            code='system',
            status=True,
            module=ScheduleQueueModule.DEFAULT,
            name='系统任务',
        )
        self.test = self.model(
            code=self.status_params_mapping[ScheduleStatus.TEST.value],
            status=True,
            module=ScheduleQueueModule.DEFAULT,
            name='测试任务',
        )
        try:
            for m in self.model.objects.filter(status=True):
                self.add(m)
        except (ProgrammingError, OperationalError):
            pass
        super(ScheduleQueues, self).__init__()

    def add(self, instance: ScheduleQueue, key=None):
        if instance.status:
            old = self.get(instance.code)
            if not old or old.module != instance.module or old.config != instance.config:
                # 如果使用的本地Socket队列，则需要检查socket队列服务是否启动，如果没有启动，则启动
                # if instance.module == ScheduleQueueModule.get_default():
                #     from django_common_task_system.cache_service import ensure_server_running
                #     ensure_server_running()
                instance.queue = import_string(instance.module)(**instance.config)
                self[instance.code] = instance
                self.__dict__[instance.code] = instance
        elif not instance.status:
            self.pop(instance.code, None)

    def delete(self, instance: ScheduleQueue, key=None):
        self.pop(instance.code, None)


class ScheduleProducers(BuiltinModels):
    model = ScheduleProducer
    model_unique_kwargs = ['queue']

    def __init__(self, queues: ScheduleQueues):
        self.opening = self.model(
            queue=queues.opening,
            lte_now=True,
            filters={
                'status': ScheduleStatus.OPENING.value,
            },
            status=True,
            name='默认',
        )
        self.test = self.model(
            queue=queues.test,
            lte_now=True,
            filters={
                'status': ScheduleStatus.TEST.value,
            },
            status=True,
            name='测试',
        )
        self.system = self.model(
            queue=queues.system,
            lte_now=True,
            filters={
                'status': ScheduleStatus.AUTO.value,
            },
            status=True,
            name='系统',
        )
        try:
            for m in self.model.objects.filter(status=True):
                self.add(m)
        except (ProgrammingError, OperationalError):
            pass
        super(ScheduleProducers, self).__init__()

    def add(self, instance: ScheduleProducer, key=None):
        if instance.status:
            old = self.get(instance.id)
            if not old or old.queue != instance.queue:
                self[instance.id] = instance
        elif not instance.status:
            self.pop(instance.id, None)

    def delete(self, instance: ScheduleProducer, key=None):
        self.pop(instance.id, None)


class ScheduleQueuePermissions(BuiltinModels):
    model = ScheduleQueuePermission
    model_unique_kwargs = ['queue', 'type']

    def __init__(self):
        super(ScheduleQueuePermissions, self).__init__()
        try:
            for m in self.model.objects.filter(status=True):
                self.add(m)
        except (ProgrammingError, OperationalError):
            pass

    def add(self, instance: ScheduleQueuePermission, key=None):
        if instance.status:
            old = self.get(instance.queue.code)
            if not old or old.type != instance.type or old.config != instance.config:
                validator = ConsumerPermissionValidator.get(instance.type)
                if validator:
                    self[instance.queue.code] = validator(instance.config)
        elif not instance.status:
            self.pop(instance.queue.code, None)

    def delete(self, instance: ScheduleQueuePermission, key=None):
        self.pop(instance.queue.code, None)


class Tasks(BuiltinModels):
    model = TaskModel
    model_unique_kwargs = ['name', 'parent', 'category']

    def __init__(self, categories: Categories, queues):
        self.shell_execution = self.model(
            name='Shell执行',
            category=categories.system_base,
            config={
                'required_fields': ['script'],
            }
        )
        self.sql_execution = self.model(
            name='SQL执行',
            category=categories.system_base,
            config={
                'required_fields': ['script'],
            }
        )

        self.sql_produce = self.model(
            name='SQL生产',
            category=categories.system_base,
            config={
                'required_fields': ['script', 'queue'],
            }
        )

        self.strict_schedule_handle = self.model(
            name='严格模式计划处理',
            category=categories.system_task,
        )

        self.custom_program = self.model(
            name='自定义程序',
            category=categories.system_base,
            config={
                'required_fields': ['custom_program']
            }
        )

        interval = 1
        unit = 'month'
        self.log_clean = self.model(
            name='日志清理',
            parent=self.sql_execution,
            category=categories.system_task,
            config={
                'script': 'delete from %s where create_time < date_sub(now(), interval %s %s);' %
                       (ScheduleLogModel._meta.db_table, interval, unit)
            },
        )

        max_retry_times = 5
        self.exception_handle = self.model(
            name='异常处理',
            category=categories.system_task,
            config={
                'max_retry_times': max_retry_times,
            },
        )
        self.test_sql_execution = self.model(
            name='测试SQL执行任务',
            parent=self.sql_execution,
            category=categories.system_test,
            config={
                'script': 'select * from %s limit 10;' % ScheduleLogModel._meta.db_table
            },
        )

        self.test_sql_produce = self.model(
            name='测试SQL生产任务',
            parent=self.sql_produce,
            category=categories.system_test,
            config={
                'script': 'select * from %s limit 10;' % ScheduleLogModel._meta.db_table,
                'queue': queues.test.code
            },
        )
        self.test_shell_execution = self.model(
            name='测试Shell执行任务',
            parent=self.shell_execution,
            category=categories.system_test,
            config={
                'script': 'echo "hello world"'
            },
        )

        executable_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../static/custom_programs'))
        self.test_python_custom_program = self.model(
            name='测试自定义Python程序执行任务',
            parent=self.custom_program,
            category=categories.system_test,
            config={
                'custom_program': {
                    'executable': os.path.join(executable_path, 'python_test.py')
                }
            }
        )
        self.test_shell_custom_program = self.model(
            name='测试自定义Shell程序执行任务',
            parent=self.custom_program,
            category=categories.system_test,
            config={
                'custom_program': {
                    'executable': os.path.join(executable_path, 'shell_test.sh')
                }
            }
        )
        self.test_zip_execute_program = self.model(
            name='测试自定义zip程序执行任务',
            parent=self.custom_program,
            category=categories.system_test,
            config={
                'custom_program': {
                    'executable': os.path.join(executable_path, 'zip_test.zip')
                }
            }
        )
        super(Tasks, self).__init__()


class Schedules(BuiltinModels):
    model_unique_kwargs = ['task']
    model = ScheduleModel

    def __init__(self, tasks: Tasks):
        self.log_clean = self.model(
            status=ScheduleStatus.AUTO,
            task=tasks.log_clean,
            config={
                "T": {
                    "DAY": {
                        "period": 1
                    },
                    "time": "01:00:00",
                    "type": "DAY"
                },
                "base_on_now": True,
                "schedule_type": "T"
            }
        )

        self.exception_handle = self.model(
            task=tasks.exception_handle,
            status=ScheduleStatus.AUTO,
            config={
                "S": {
                    "period": 60,
                    "schedule_start_time": "2023-04-04 15:31:00"
                },
                "base_on_now": True,
                "schedule_type": "S"
            }
        )

        config = {
            "S": {
                "period": 60,
                "schedule_start_time": "2023-04-04 15:31:00"
            },
            "base_on_now": True,
            "schedule_type": "S"
        }

        self.test_sql_execution = self.model(
            task=tasks.test_sql_execution,
            status=ScheduleStatus.TEST.value,
            config=config
        )
        self.test_sql_produce = self.model(
            task=tasks.test_sql_produce,
            status=ScheduleStatus.TEST.value,
            config=config
        )
        self.test_shell_execution = self.model(
            task=tasks.test_shell_execution,
            status=ScheduleStatus.TEST.value,
            config=config
        )
        self.test_python_custom_program = self.model(
            task=tasks.test_python_custom_program,
            status=ScheduleStatus.TEST.value,
            config=config
        )
        self.test_shell_custom_program = self.model(
            task=tasks.test_shell_custom_program,
            status=ScheduleStatus.TEST.value,
            config=config
        )
        self.test_zip_execute_program = self.model(
            task=tasks.test_zip_execute_program,
            status=ScheduleStatus.TEST.value,
            config=config
        )

        self.strict_schedule_handle = self.model(
            task=tasks.strict_schedule_handle,
            status=ScheduleStatus.AUTO.value,
            config={
                "S": {
                    "period": 60 * 60,
                    "schedule_start_time": "2023-04-04 15:31:00"
                },
                "base_on_now": True,
                "schedule_type": "S"
            }
        )

        super(Schedules, self).__init__()


class Builtins:

    def __init__(self):
        self._initialized = False
        self.categories = Categories()
        self.schedule_queues = ScheduleQueues()
        self.schedule_producers = ScheduleProducers(self.schedule_queues)
        self.tasks = Tasks(self.categories, self.schedule_queues)
        self.schedules = Schedules(self.tasks)
        self.schedule_queue_permissions = ScheduleQueuePermissions()

    @staticmethod
    def init_user():
        user = UserModel.objects.filter(is_superuser=True).order_by('id').first()
        if not user:
            raise Exception('请先创建超级用户')
        for field in user._meta.fields:
            setattr(DEFAULT_USER, field.name, getattr(user, field.name))

    def initialize(self):
        if not self._initialized:
            self._initialized = True
            if os.environ.get('RUN_MAIN') == 'true' and (os.environ.get('USE_GUNICORN') or 'true') == 'true' and os.environ.get('RUN_CLIENT') != 'true':
                print('初始化内置任务...')
                self.init_user()
                for i in self.__dict__.values():
                    if isinstance(i, BuiltinModels):
                        i.initialize()
                from threading import Timer
                Timer(2, function=system_initialized_signal.send, args=('system_initialized', )).start()


builtins = Builtins()
builtins.initialize()
