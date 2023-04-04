from django.db import models
from django.conf import settings
from django_common_task_system.models import AbstractTask, AbstractTaskSchedule, AbstractTaskScheduleLog
from .choices import SystemTaskType, ScheduleQueueModule
from django_common_objects.models import CommonCategory


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

    @property
    def default_category(self):
        return CommonCategory.objects.get_or_create(
            name='系统任务',
            model=self._meta.label,
            user_id=self.user_id,
        )[0]

    @property
    def log_cleaning_task(self):
        config = self.config.get('log_cleaning', {})
        interval = config.get('interval', 1)
        unit = config.get('unit', 'month')
        return self.objects.get_or_create(
            name='日志清理',
            user_id=self.user_id,
            defaults={
                'category': self.default_category,
                'task_type': SystemTaskType.SQL_TASK_EXECUTION.value,
                'config': {
                   'sql': 'delete from %s where create_time < date_sub(now(), interval %s %s);' %
                          (models.SystemScheduleLog._meta.db_table, interval, unit)
                },
            }
        )[0]

    @property
    def exception_handling_task(self):
        config = self.config.get('exception_handling', {})
        max_retry_times = config.get('max_retry_times', 5)
        return self.objects.get_or_create(
            name='异常处理',
            user_id=self.user_id,
            defaults={
                'category': self.default_category,
                'task_type': SystemTaskType.CUSTOM.value,
                'config': {
                    'max_retry_times': max_retry_times,
                },
            }
        )[0]

    class Meta(AbstractTask.Meta):
        abstract = 'django_common_task_system.system_task' not in settings.INSTALLED_APPS
        db_table = 'system_task'
        verbose_name = verbose_name_plural = '系统任务'

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        if self.category_id is None:
            self.category = self.default_category
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

    @property
    def log_cleaning_schedule(self):
        return self.objects.get_or_create(
            task=self.task.log_cleaning_task,
            user_id=self.user_id,
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

    @property
    def exception_handling_schedule(self):
        return self.objects.get_or_create(
            task=self.task.exception_handling_task,
            user_id=self.user_id,
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
