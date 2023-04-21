from django.db import models
from django.conf import settings
from django_common_task_system.choices import ScheduleQueueModule, TaskScheduleStatus, ConsumerPermissionType
from django_common_task_system.models import (
    AbstractTask, AbstractTaskSchedule, AbstractTaskScheduleLog, TaskScheduleLog, AbstractScheduleCallback, 
    AbstractTaskScheduleProducer, AbstractTaskScheduleQueue, AbstractConsumerPermission, AbstractExceptionReport,
    BaseBuiltinQueues, BaseBuiltinProducers, BaseConsumerPermissions, BaseBuiltins,
    BuiltinModels
)
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
            self.category = builtins.categories.system_default_category
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


class SystemConsumerPermission(AbstractConsumerPermission):
    producer = models.ForeignKey(SystemScheduleProducer, db_constraint=False,
                                 on_delete=models.CASCADE, verbose_name='生产者')

    class Meta(AbstractConsumerPermission.Meta):
        db_table = 'system_consumer_permission'
        abstract = 'django_common_task_system.system_task' not in settings.INSTALLED_APPS


class SystemExceptionReport(AbstractExceptionReport):

    class Meta(AbstractExceptionReport.Meta):
        db_table = 'system_exception_report'
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
                'required_fields': ['shell'],
            }
        )
        self.sql_execution_parent_task = self.model(
            name='SQL执行',
            user=user,
            category=categories.system_base_category,
            config={
                'required_fields': ['sql'],
            }
        )

        self.sql_produce_parent_task = self.model(
            name='SQL生产',
            user=user,
            category=categories.system_base_category,
            config={
                'required_fields': ['sql', 'queue'],
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
                'sql': 'delete from %s where create_time < date_sub(now(), interval %s %s);' %
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
                'sql': 'delete from %s where create_time < date_sub(now(), interval %s %s);' %
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
                'sql': 'select * from %s limit 10;' % SystemScheduleLog._meta.db_table
            },
            user=user
        )

        self.test_sql_produce = self.model(
            name='测试SQL生产任务',
            parent=self.sql_produce_parent_task,
            category=categories.system_test_category,
            config={
                'sql': 'select * from %s limit 10;' % SystemScheduleLog._meta.db_table,
                'queue': queues.test.code
            },
            user=user
        )
        self.test_shell_execution = self.model(
            name='测试Shell执行任务',
            parent=self.shell_execution_parent_task,
            category=categories.system_test_category,
            config={
                'shell': 'echo "hello world"'
            },
            user=user
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
            'config': {
                "S": {
                    "period": 60,
                    "schedule_start_time": "2023-04-04 15:31:00"
                },
                "base_on_now": True,
                "schedule_type": "S"
            }
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
