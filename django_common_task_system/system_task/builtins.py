from django_common_task_system.choices import ScheduleQueueModule, TaskScheduleStatus, ConsumerPermissionType
from django_common_task_system.models import (
    AbstractTaskSchedule, TaskScheduleLog,
    BaseBuiltinQueues, BaseBuiltinProducers, BaseConsumerPermissions, BaseBuiltins, UserModel,
    BuiltinModels
)
from django_common_objects.models import CommonCategory
from django_common_task_system.system_task.models import SystemTask, SystemScheduleProducer, SystemSchedule, \
    SystemConsumerPermission, SystemScheduleLog, SystemScheduleQueue
from django_common_task_system import get_schedule_log_model, get_task_schedule_model


class BuiltinCategories(BuiltinModels):
    model = CommonCategory
    model_unique_kwargs = ('name',)

    def __init__(self, user):
        model = SystemTask._meta.label
        self.system_default_category = self.model(
            name='系统任务',
            model=model,
            user=user,
        )

        self.system_base_category = self.model(
            name='系统基础',
            model=model,
            user=user,
        )

        self.system_test_category = self.model(
            name='系统测试',
            model=model,
            user=user,
        )
        super(BuiltinCategories, self).__init__()


class BuiltinQueues(BaseBuiltinQueues):
    model = SystemScheduleQueue

    def __init__(self):
        self.opening = self.model(
            code=self.status_params_mapping[TaskScheduleStatus.OPENING.value],
            status=True,
            module=ScheduleQueueModule.QUEUE.value,
            name='系统任务队列'
        )

        self.test = self.model(
            code=self.status_params_mapping[TaskScheduleStatus.TEST.value],
            status=True,
            module=ScheduleQueueModule.QUEUE.value,
            name='测试任务队列'
        )
        super(BuiltinQueues, self).__init__()


class BuiltinProducers(BaseBuiltinProducers):
    model = SystemScheduleProducer

    def __init__(self, queues: BuiltinQueues):
        self.opening = self.model(
            queue=queues.opening,
            lte_now=True,
            filters={
                'status': TaskScheduleStatus.OPENING.value,
            },
            status=True,
            name='默认'
        )
        self.test = self.model(
            queue=queues.test,
            lte_now=True,
            filters={
                'status': TaskScheduleStatus.TEST.value,
            },
            status=True,
            name='测试'
        )
        super(BuiltinProducers, self).__init__()


class BuiltinTasks(BuiltinModels):
    model = SystemTask
    model_unique_kwargs = ['name', 'user', 'parent', 'category']

    def __init__(self, categories: BuiltinCategories, queues: BuiltinQueues):
        user = categories.system_default_category.user

        self.shell_execution_parent_task = self.model(
            name='Shell执行',
            user=user,
            category=categories.system_base_category,
            config={
                'required_fields': ['script'],
            }
        )
        self.sql_execution_parent_task = self.model(
            name='SQL执行',
            user=user,
            category=categories.system_base_category,
            config={
                'required_fields': ['script'],
            }
        )

        self.sql_produce_parent_task = self.model(
            name='SQL生产',
            user=user,
            category=categories.system_base_category,
            config={
                'required_fields': ['script', 'queue'],
            }
        )

        self.strict_schedule_parent_task = self.model(
            name='严格模式计划处理',
            user=user,
            category=categories.system_base_category,
            config={
                'required_fields': ['queue']
            }
        )

        interval = 1
        unit = 'month'
        self.system_log_cleaning = self.model(
            name='系统日志清理',
            parent=self.sql_execution_parent_task,
            category=categories.system_default_category,
            user=user,
            config={
                'script': 'delete from %s where create_time < date_sub(now(), interval %s %s);' %
                       (SystemScheduleLog._meta.db_table, interval, unit)
            },
        )

        max_retry_times = 5
        self.system_exception_handling = self.model(
            name='系统异常处理',
            user=user,
            category=categories.system_default_category,
            config={
                'max_retry_times': max_retry_times,
            },
        )

        interval = 1
        unit = 'month'
        self.task_log_cleaning = self.model(
            name='任务日志清理',
            user=user,
            category=categories.system_default_category,
            parent=self.sql_execution_parent_task,
            config={
                'script': 'delete from %s where create_time < date_sub(now(), interval %s %s);' %
                       (TaskScheduleLog._meta.db_table, interval, unit)
            },
        )

        max_retry_times = 5
        self.task_exception_handling = self.model(
            name='任务异常处理',
            user=user,
            category=categories.system_default_category,
            config={
                'max_retry_times': max_retry_times,
            },
        )

        self.test_sql_execution = self.model(
            name='测试SQL执行任务',
            parent=self.sql_execution_parent_task,
            category=categories.system_test_category,
            config={
                'script': 'select * from %s limit 10;' % SystemScheduleLog._meta.db_table
            },
            user=user
        )

        self.test_sql_produce = self.model(
            name='测试SQL生产任务',
            parent=self.sql_produce_parent_task,
            category=categories.system_test_category,
            config={
                'script': 'select * from %s limit 10;' % SystemScheduleLog._meta.db_table,
                'queue': queues.test.code
            },
            user=user
        )
        self.test_shell_execution = self.model(
            name='测试Shell执行任务',
            parent=self.shell_execution_parent_task,
            category=categories.system_test_category,
            config={
                'script': 'echo "hello world"'
            },
            user=user
        )

        def get_model_related(model, parent='', excludes=None):
            related = []
            for field in model._meta.fields:
                t = field.__class__.__name__
                if t == 'ForeignKey' and parent.split("__")[-1] != field.name:
                    if excludes and field.related_model in excludes:
                        continue
                    if parent:
                        child = parent + "__" + field.name
                    else:
                        child = field.name
                    related.append(child)
                    related.extend(get_model_related(field.related_model, parent=child, excludes=excludes))
            return related

        self.system_strict_schedule_process = self.model(
            name='系统严格模式任务处理',
            parent=self.strict_schedule_parent_task,
            category=categories.system_default_category,
            user=user,
            config={
                'schedule_model': SystemSchedule.__module__ + "." + SystemSchedule.__name__,
                'log_model': SystemScheduleLog.__module__ + "." + SystemScheduleLog.__name__,
                'related': ['task', 'callback'],
            }
        )
        task_schedule = get_task_schedule_model()
        log_model = get_schedule_log_model()
        self.task_strict_schedule_process = self.model(
            name='普通任务严格模式任务处理',
            parent=self.strict_schedule_parent_task,
            category=categories.system_default_category,
            user=user,
            config={
                'schedule_model': task_schedule.__module__ + "." + task_schedule.__name__,
                'log_model': log_model.__module__ + "." + log_model.__name__,
                'related': get_model_related(task_schedule, excludes=[UserModel, CommonCategory]),
            }
        )
        super(BuiltinTasks, self).__init__()


class BuiltinSchedules(BuiltinModels):
    model_unique_kwargs = ['task', 'user']
    model = SystemSchedule

    def __init__(self, user, tasks: BuiltinTasks):
        self.system_log_cleaning = self.model(
            task=tasks.system_log_cleaning,
            user=user,
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

        self.system_exception_handling = self.model(
            task=tasks.system_exception_handling,
            user=user,
            config={
                "S": {
                    "period": 60,
                    "schedule_start_time": "2023-04-04 15:31:00"
                },
                "base_on_now": True,
                "schedule_type": "S"
            }
        )

        self.task_log_cleaning = self.model(
            task=tasks.task_log_cleaning,
            user=user,
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

        self.task_exception_handling = self.model(
            task=tasks.task_exception_handling,
            user=user,
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
            user=user,
            status=TaskScheduleStatus.TEST.value,
            config=config
        )
        self.test_sql_produce = self.model(
            task=tasks.test_sql_produce,
            user=user,
            status=TaskScheduleStatus.TEST.value,
            config=config
        )
        self.test_shell_execution = self.model(
            task=tasks.test_shell_execution,
            user=user,
            status=TaskScheduleStatus.TEST.value,
            config=config
        )

        self.system_strict_schedule_process = self.model(
            task=tasks.system_strict_schedule_process,
            user=user,
            status=TaskScheduleStatus.OPENING.value,
            config={
                "S": {
                    "period": 60 * 60,
                    "schedule_start_time": "2023-04-04 15:31:00"
                },
                "base_on_now": True,
                "schedule_type": "S"
            }
        )

        self.task_strict_schedule_process = self.model(
            task=tasks.task_strict_schedule_process,
            user=user,
            status=TaskScheduleStatus.OPENING.value,
            config={
                "S": {
                    "period": 60 * 60,
                    "schedule_start_time": "2023-04-04 15:31:00"
                },
                "base_on_now": True,
                "schedule_type": "S"
            }
        )
        super(BuiltinSchedules, self).__init__()


class BuiltinConsumerPermissions(BaseConsumerPermissions):
    model = SystemConsumerPermission

    def __init__(self, producers: BuiltinProducers):
        self.system_consumer_permission = self.model(
            producer=producers.opening,
            type=ConsumerPermissionType.IP_WHITE_LIST.value,
            status=True,
            config={
                'ip_whitelist': ['127.0.0.1']
            }
        )
        super(BuiltinConsumerPermissions, self).__init__()


class Builtins(BaseBuiltins):
    app = 'django_common_task_system.system_task'

    def __init__(self):
        super(Builtins, self).__init__()
        self.queues = BuiltinQueues()
        self.categories = BuiltinCategories(self.user)
        self.tasks = BuiltinTasks(self.categories, self.queues)
        self.schedules = BuiltinSchedules(self.user, self.tasks)
        self.producers = BuiltinProducers(self.queues)
        self.consumer_permissions = BuiltinConsumerPermissions(self.producers)


builtins = Builtins()
