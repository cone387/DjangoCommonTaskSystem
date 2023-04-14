from django.db import models
from django.conf import settings
from django.utils.module_loading import import_string

from django_common_task_system.choices import ScheduleQueueModule, TaskScheduleStatus
from django_common_task_system.models import AbstractTask, AbstractTaskSchedule, AbstractTaskScheduleLog, \
    TaskScheduleLog, AbstractScheduleCallback, \
    AbstractTaskScheduleProducer, AbstractTaskScheduleQueue, BaseBuiltinQueues
from django_common_objects.models import CommonCategory
from django.contrib.auth import get_user_model

User = get_user_model()


class SystemTask(AbstractTask):

    class Meta(AbstractTask.Meta):
        abstract = 'django_common_task_system.system_task' not in settings.INSTALLED_APPS
        db_table = 'system_task'
        verbose_name = verbose_name_plural = '系统任务'

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        if self.category_id is None:
            self.category = builtins.tasks.system_default_category
        super().save(force_insert, force_update, using, update_fields)


class SystemScheduleQueue(AbstractTaskScheduleQueue):

    class Meta(AbstractTaskScheduleQueue.Meta):
        db_table = 'system_schedule_queue'
        verbose_name = verbose_name_plural = '系统队列'
        abstract = 'django_common_task_system.system_task' not in settings.INSTALLED_APPS


class SystemScheduleCallback(AbstractScheduleCallback):
    queue = models.ForeignKey(SystemScheduleQueue, db_constraint=False, related_name='callbacks',
                              on_delete=models.CASCADE, verbose_name='队列')

    class Meta(AbstractScheduleCallback.Meta):
        db_table = 'system_schedule_callback'
        verbose_name = verbose_name_plural = '系统回调'
        abstract = 'django_common_task_system.system_task' not in settings.INSTALLED_APPS


class SystemSchedule(AbstractTaskSchedule):
    task = models.ForeignKey(SystemTask, db_constraint=False, related_name='schedules',
                             on_delete=models.CASCADE, verbose_name='任务')
    callback = models.ForeignKey(SystemScheduleCallback, on_delete=models.CASCADE,
                                 null=True, blank=True, db_constraint=False, verbose_name='回调')

    class Meta(AbstractTaskSchedule.Meta):
        db_table = 'system_schedule'
        verbose_name = verbose_name_plural = '系统计划'
        ordering = ('-update_time',)
        abstract = 'django_common_task_system.system_task' not in settings.INSTALLED_APPS


class SystemScheduleProducer(AbstractTaskScheduleProducer):
    queue = models.ForeignKey(SystemScheduleQueue, db_constraint=False, related_name='producers',
                              on_delete=models.CASCADE, verbose_name='队列')

    class Meta(AbstractTaskScheduleProducer.Meta):
        db_table = 'system_schedule_producer'
        verbose_name = verbose_name_plural = '计划生产'
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
    process_id = models.PositiveIntegerField(verbose_name='进程ID', unique=True)
    process_name = models.CharField(max_length=100, verbose_name='进程名称')
    env = models.CharField(max_length=500, verbose_name='环境变量', blank=True, null=True)
    status = models.BooleanField(default=True, verbose_name='状态')
    log_file = models.CharField(max_length=200, verbose_name='日志文件')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'system_process'
        verbose_name = verbose_name_plural = '系统进程'

    def __str__(self):
        return "%s(%s)" % (self.process_name, self.process_id)


class BuiltinQueues(BaseBuiltinQueues):
    model = SystemScheduleQueue

    def __init__(self):
        self.opening: SystemScheduleQueue = self.model.objects.get_or_create(
            code=self.status_params_mapping[TaskScheduleStatus.OPENING.value],
            defaults={
                'status': True,
                'module': ScheduleQueueModule.QUEUE.value,
                'name': '系统任务队列'
            }
        )[0]

        self.test = self.model.objects.get_or_create(
            code=self.status_params_mapping[TaskScheduleStatus.TEST.value],
            defaults={
                'status': True,
                'module': ScheduleQueueModule.QUEUE.value,
                'name': '测试任务队列'
            }
        )[0]
        super(BuiltinQueues, self).__init__()


class BuiltinProducers:

    def __init__(self, queues: BuiltinQueues):
        self.opening = SystemScheduleProducer.objects.get_or_create(
            queue=queues.opening,
            lte_now=True,
            defaults={
                'filters': {
                    'status': TaskScheduleStatus.OPENING.value,
                },
                'status': True,
                'name': '默认'
            }
        )[0]
        self.test = SystemScheduleProducer.objects.get_or_create(
            queue=queues.test,
            lte_now=True,
            defaults={
                'filters': {
                    'status': TaskScheduleStatus.TEST.value,
                },
                'status': True,
                'name': '测试'
            }
        )[0]


class BuiltinTasks:

    def __init__(self, user, queues: BuiltinQueues):
        self.system_default_category = CommonCategory.objects.get_or_create(
            name='系统任务',
            model=SystemTask._meta.label,
            user=user,
        )[0]

        self.system_base_category = CommonCategory.objects.get_or_create(
            name='系统基础',
            model=SystemTask._meta.label,
            user=user,
        )[0]

        self.system_test_category = CommonCategory.objects.get_or_create(
            name='系统测试',
            model=SystemTask._meta.label,
            user=user,
        )[0]

        self.shell_execution_parent_task = SystemTask.objects.get_or_create(
            name='Shell执行',
            user=user,
            category=self.system_base_category,
            defaults={
                'config': {
                    'required_fields': ['shell'],
                }
            },
        )[0]

        self.sql_execution_parent_task = SystemTask.objects.get_or_create(
            name='SQL执行',
            user=user,
            category=self.system_base_category,
            defaults={
                'config': {
                    'required_fields': ['sql'],
                }
            },
        )[0]

        self.sql_produce_parent_task = SystemTask.objects.get_or_create(
            name='SQL生产',
            user=user,
            category=self.system_base_category,
            defaults={
                'config': {
                    'required_fields': ['sql', 'queue'],
                }
            },
        )[0]

        interval = 1
        unit = 'month'
        self.system_log_cleaning = SystemTask.objects.get_or_create(
            name='系统日志清理',
            parent=self.shell_execution_parent_task,
            category=self.system_default_category,
            user=user,
            defaults={
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
            category=self.system_default_category,
            defaults={
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
            category=self.system_default_category,
            parent=self.shell_execution_parent_task,
            defaults={
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
            category=self.system_default_category,
            defaults={
                'config': {
                    'max_retry_times': max_retry_times,
                },
            }
        )[0]

        self.test_sql_execution = SystemTask.objects.get_or_create(
            name='测试SQL执行任务',
            parent=self.sql_execution_parent_task,
            category=self.system_test_category,
            config={
                'sql': 'select * from %s limit 10;' % SystemScheduleLog._meta.db_table
            },
            user=user
        )[0]

        self.test_sql_produce = SystemTask.objects.get_or_create(
            name='测试SQL生产任务',
            parent=self.sql_produce_parent_task,
            category=self.system_test_category,
            config={
                'sql': 'select * from %s limit 10;' % SystemScheduleLog._meta.db_table,
                'queue': queues.test.code
            },
            user=user
        )[0]
        self.test_shell_execution = SystemTask.objects.get_or_create(
            name='测试Shell执行任务',
            parent=self.shell_execution_parent_task,
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
        self._queues = None
        self._producers = None

    def initialize(self):
        if not self._initialized:
            print('初始化系统内置任务')
            self._initialized = True
            user = User.objects.filter(is_superuser=True).order_by('id').first()
            if not user:
                raise Exception('未找到超级管理员')
            self._queues = BuiltinQueues()
            self._producers = BuiltinProducers(self._queues)
            self._tasks = BuiltinTasks(user, self._queues)
            self._schedules = BuiltinSchedules(user, self._tasks)

    @property
    def tasks(self) -> BuiltinTasks:
        self.initialize()
        return self._tasks

    @property
    def schedules(self) -> BuiltinSchedules:
        self.initialize()
        return self._schedules

    @property
    def queues(self) -> BuiltinQueues:
        self.initialize()
        return self._queues

    @property
    def producers(self) -> BuiltinProducers:
        self.initialize()
        return self._producers


builtins = Builtins()
