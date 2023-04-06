from django.core.exceptions import AppRegistryNotReady
from django.db import models
from django.conf import settings
from django_common_task_system.models import AbstractTask, AbstractTaskSchedule, AbstractTaskScheduleLog, \
    Task, TaskSchedule, TaskScheduleLog
from .choices import SystemTaskType, ScheduleQueueModule
from django_common_objects.models import CommonCategory
from django.contrib.auth import get_user_model

User = get_user_model()


def code_validator(value):
    import re
    from django.core.validators import ValidationError
    if re.match(r'[a-zA-Z_-]+', value) is None:
        raise ValidationError('编码只能包含字母、数字、下划线和中划线')


class SystemTask(AbstractTask):

    tags = None
    task_type = models.CharField(max_length=32, verbose_name='任务类型',
                                 default=SystemTaskType.SQL_TASK_PRODUCE.value,
                                 choices=SystemTaskType.choices)

    class Meta(AbstractTask.Meta):
        abstract = 'django_common_task_system.system_task' not in settings.INSTALLED_APPS
        db_table = 'system_task'
        verbose_name = verbose_name_plural = '系统任务'

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        if self.category_id is None:
            self.category = builtins.tasks.system_category
        super().save(force_insert, force_update, using, update_fields)


class SystemScheduleQueue(models.Model):
    id = models.AutoField(primary_key=True, verbose_name='ID')
    name = models.CharField(max_length=100, verbose_name='队列名称', unique=True)
    code = models.CharField(max_length=100, verbose_name='队列编码', unique=True, validators=[code_validator])
    status = models.BooleanField(default=True, verbose_name='状态')
    module = models.CharField(max_length=100, verbose_name='队列类型',
                              default=ScheduleQueueModule.QUEUE,
                              choices=ScheduleQueueModule.choices)
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    @classmethod
    def get_or_create_default(cls) -> 'SystemScheduleQueue':
        o, _ = SystemScheduleQueue.objects.get_or_create(code='system', name='系统队列')
        return o

    class Meta:
        db_table = 'system_schedule_queue'
        verbose_name = verbose_name_plural = '系统队列'
        abstract = 'django_common_task_system.system_task' not in settings.INSTALLED_APPS

    def __str__(self):
        return "%s(%s)" % (self.name, self.code)


class SystemSchedule(AbstractTaskSchedule):
    task = models.ForeignKey(SystemTask, db_constraint=False, related_name='schedules',
                             on_delete=models.CASCADE, verbose_name='任务')

    class Meta(AbstractTaskSchedule.Meta):
        db_table = 'system_schedule'
        verbose_name = verbose_name_plural = '系统计划'
        ordering = ('-update_time',)
        abstract = 'django_common_task_system.system_task' not in settings.INSTALLED_APPS


class SystemScheduleLog(AbstractTaskScheduleLog):
    schedule = models.ForeignKey(SystemSchedule, db_constraint=False, related_name='logs',
                                 on_delete=models.CASCADE, verbose_name='任务计划')

    class Meta(AbstractTaskScheduleLog.Meta):
        db_table = 'system_schedule_log'
        verbose_name = verbose_name_plural = '系统日志'
        ordering = ('-schedule_time',)
        abstract = 'django_common_task_system.system_task' not in settings.INSTALLED_APPS


class SystemProcess(models.Model):
    id = models.AutoField(primary_key=True, verbose_name='ID')
    container_id = models.CharField(max_length=100, verbose_name='容器ID', unique=True)
    container_name = models.CharField(max_length=100, verbose_name='容器名称', unique=True)
    env = models.JSONField(verbose_name='环境变量', default=dict)
    status = models.CharField(max_length=100, verbose_name='状态', default='running')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'system_process'
        verbose_name = verbose_name_plural = '系统进程'

    def __str__(self):
        return "%s(%s)" % (self.container_id, self.container_name)


class BuiltinTasks:

    def __init__(self, user):
        self.system_default_category = CommonCategory.objects.get_or_create(
            name='系统任务',
            model=SystemTask._meta.label,
            user=user,
        )[0]

        self.system_test_category = CommonCategory.objects.get_or_create(
            name='系统测试',
            model=SystemTask._meta.label,
            user=user,
        )[0]

        interval = 1
        unit = 'month'
        self.system_log_cleaning = SystemTask.objects.get_or_create(
            name='系统日志清理',
            user=user,
            defaults={
                'category': self.system_default_category,
                'task_type': SystemTaskType.SQL_TASK_EXECUTION.value,
                'config': {
                    'sql': 'delete from %s where create_time < date_sub(now(), interval %s %s);' %
                           (SystemScheduleLog._meta.db_table, interval, unit)
                },
            }
        )[0]

        max_retry_times = 5
        self.system_exception_handling = SystemTask.objects.get_or_create(
            name='系统异常处理',
            user=user,
            defaults={
                'category': self.system_default_category,
                'task_type': SystemTaskType.CUSTOM.value,
                'config': {
                    'max_retry_times': max_retry_times,
                },
            }
        )[0]

        interval = 1
        unit = 'month'
        self.task_log_cleaning = SystemTask.objects.get_or_create(
            name='任务日志清理',
            user=user,
            defaults={
                'category': self.system_default_category,
                'task_type': SystemTaskType.SQL_TASK_EXECUTION.value,
                'config': {
                    'sql': 'delete from %s where create_time < date_sub(now(), interval %s %s);' %
                           (TaskScheduleLog._meta.db_table, interval, unit)
                },
            }
        )[0]

        max_retry_times = 5
        self.task_exception_handling = SystemTask.objects.get_or_create(
            name='任务异常处理',
            user=user,
            defaults={
                'category': self.system_default_category,
                'task_type': SystemTaskType.CUSTOM.value,
                'config': {
                    'max_retry_times': max_retry_times,
                },
            }
        )[0]

        self.test_sql_execution = SystemTask.objects.get_or_create(
            name='测试SQL执行任务',
            task_type=SystemTaskType.SQL_TASK_EXECUTION.value,
            category=self.system_test_category,
            config={
                'sql': 'select * from %s limit 10;' % SystemScheduleLog._meta.db_table
            },
            user=user
        )[0]

        self.test_sql_produce = SystemTask.objects.get_or_create(
            name='测试SQL生产任务',
            task_type=SystemTaskType.SQL_TASK_EXECUTION.value,
            category=self.system_test_category,
            config={
                'sql': 'select * from %s limit 10;' % SystemScheduleLog._meta.db_table
            },
            user=user
        )[0]
        self.test_shell_execution = SystemTask.objects.get_or_create(
            name='测试Shell执行任务',
            task_type=SystemTaskType.SHELL_EXECUTION.value,
            category=self.system_test_category,
            config={
                'shell': 'echo "hello world"'
            },
            user=user
        )[0]


class BuiltinSchedules:

    def __init__(self, user, tasks: BuiltinTasks):
        self.system_log_cleaning = SystemSchedule.objects.get_or_create(
            task=tasks.system_log_cleaning,
            user=user,
            defaults={
                'config': {
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
            },
        )[0]

        self.system_exception_handling = SystemSchedule.objects.get_or_create(
            task=tasks.system_exception_handling,
            user=user,
            defaults={
                'config': {
                    "S": {
                        "period": 60,
                        "schedule_start_time": "2023-04-04 15:31:00"
                    },
                    "base_on_now": True,
                    "schedule_type": "S"
                }
            }
        )[0]

        self.task_log_cleaning = SystemSchedule.objects.get_or_create(
            task=tasks.task_log_cleaning,
            user=user,
            defaults={
                'config': {
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
            }
        )[0]

        self.task_exception_handling = SystemSchedule.objects.get_or_create(
            task=tasks.task_exception_handling,
            user=user,
            defaults={
                'config': {
                    "S": {
                        "period": 60,
                        "schedule_start_time": "2023-04-04 15:31:00"
                    },
                    "base_on_now": True,
                    "schedule_type": "S"
                }
            }
        )[0]

        defaults = {
            'config': {
                "S": {
                    "period": 60,
                    "schedule_start_time": "2023-04-04 15:31:00"
                },
                "base_on_now": True,
                "schedule_type": "S"
            }
        }

        self.test_sql_execution = SystemSchedule.objects.get_or_create(
            task=tasks.test_sql_execution,
            user=user,
            defaults=defaults
        )[0]

        self.test_sql_produce = SystemSchedule.objects.get_or_create(
            task=tasks.test_sql_produce,
            user=user,
            defaults=defaults
        )[0]
        self.test_shell_execution = SystemSchedule.objects.get_or_create(
            task=tasks.test_shell_execution,
            user=user,
            defaults=defaults
        )[0]


class Builtins:

    def __init__(self):
        self._initialized = False
        self._tasks = None
        self._schedules = None

    def initialize(self):
        if not self._initialized:
            print('初始化内置任务')
            self._initialized = True
            user = User.objects.filter(is_superuser=True).order_by('id').first()
            if not user:
                raise Exception('未找到超级管理员')
            self._tasks = BuiltinTasks(user)
            self._schedules = BuiltinSchedules(user, self.tasks)

    @property
    def tasks(self) -> BuiltinTasks:
        self.initialize()
        return self._tasks

    @property
    def schedules(self) -> BuiltinSchedules:
        self.initialize()
        return self._schedules


builtins = Builtins()
