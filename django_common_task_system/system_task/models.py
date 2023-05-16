from django.db import models
from django.conf import settings
from django_common_task_system.models import (
    AbstractTask, AbstractTaskSchedule, AbstractTaskScheduleLog, AbstractScheduleCallback,
    AbstractTaskScheduleProducer, AbstractTaskScheduleQueue, AbstractConsumerPermission, AbstractExceptionReport,
)
from django.contrib.auth import get_user_model

User = get_user_model()


class SystemTask(AbstractTask):

    class Meta(AbstractTask.Meta):
        abstract = 'django_common_task_system.system_task' not in settings.INSTALLED_APPS
        db_table = 'system_task'
        verbose_name = verbose_name_plural = '系统任务'


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
