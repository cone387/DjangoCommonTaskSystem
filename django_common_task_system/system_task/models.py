from django.db import models
from django_common_task_system.generic.models import (
    AbstractTask, AbstractTaskSchedule, AbstractTaskScheduleLog, AbstractScheduleCallback,
    AbstractTaskScheduleProducer, AbstractTaskScheduleQueue, AbstractConsumerPermission, AbstractExceptionReport,
)
from django.contrib.auth import get_user_model

User = get_user_model()


class SystemTask(AbstractTask):

    class Meta(AbstractTask.Meta):
        db_table = 'system_task'
        verbose_name = verbose_name_plural = '系统任务'


class SystemScheduleQueue(AbstractTaskScheduleQueue):

    class Meta(AbstractTaskScheduleQueue.Meta):
        db_table = 'system_schedule_queue'
        verbose_name = verbose_name_plural = '系统队列'


class SystemScheduleCallback(AbstractScheduleCallback):

    class Meta(AbstractScheduleCallback.Meta):
        db_table = 'system_schedule_callback'
        verbose_name = verbose_name_plural = '系统回调'


class SystemSchedule(AbstractTaskSchedule):
    task = models.ForeignKey(SystemTask, db_constraint=False, related_name='schedules',
                             on_delete=models.CASCADE, verbose_name='任务')
    callback = models.ForeignKey(SystemScheduleCallback, on_delete=models.CASCADE,
                                 null=True, blank=True, db_constraint=False, verbose_name='回调')

    class Meta(AbstractTaskSchedule.Meta):
        db_table = 'system_schedule'
        verbose_name = verbose_name_plural = '系统计划'
        ordering = ('-update_time',)


class SystemScheduleProducer(AbstractTaskScheduleProducer):
    queue = models.ForeignKey(SystemScheduleQueue, db_constraint=False, related_name='producers',
                              on_delete=models.CASCADE, verbose_name='队列')

    class Meta(AbstractTaskScheduleProducer.Meta):
        db_table = 'system_schedule_producer'
        verbose_name = verbose_name_plural = '计划生产'


class SystemScheduleLog(AbstractTaskScheduleLog):
    schedule = models.ForeignKey(SystemSchedule, db_constraint=False, related_name='logs',
                                 on_delete=models.CASCADE, verbose_name='任务计划')

    class Meta(AbstractTaskScheduleLog.Meta):
        db_table = 'system_schedule_log'
        verbose_name = verbose_name_plural = '系统日志'
        ordering = ('-schedule_time',)


class SystemConsumerPermission(AbstractConsumerPermission):
    producer = models.ForeignKey(SystemScheduleProducer, db_constraint=False,
                                 on_delete=models.CASCADE, verbose_name='生产者')

    class Meta(AbstractConsumerPermission.Meta):
        db_table = 'system_consumer_permission'


class SystemExceptionReport(AbstractExceptionReport):

    class Meta(AbstractExceptionReport.Meta):
        db_table = 'system_exception_report'
