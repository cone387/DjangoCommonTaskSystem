from django.db import models
from django.conf import settings
from django_common_task_system.models import AbstractTask, AbstractTaskSchedule, AbstractTaskScheduleLog
from .choices import SystemTaskType, ScheduleQueueModule


def code_validator(value):
    import re
    from django.core.validators import ValidationError
    if re.match(r'[a-zA-Z_-]+', value) is None:
        raise ValidationError('编码只能包含字母、数字、下划线和中划线')


class SystemTask(AbstractTask):

    tags = None
    task_type = models.CharField(max_length=32, verbose_name='任务类型',
                                 default=SystemTaskType.SQL_TASK_PRODUCE,
                                 choices=SystemTaskType.choices)

    class Meta(AbstractTask.Meta):
        abstract = 'django_common_task_system.system_task' not in settings.INSTALLED_APPS
        db_table = 'system_task'
        verbose_name = verbose_name_plural = '系统任务'


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
