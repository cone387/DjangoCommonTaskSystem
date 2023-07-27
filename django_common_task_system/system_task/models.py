from django.db import models
from django_common_task_system.generic import models as generic_models
from django.contrib.auth import get_user_model

User = get_user_model()


class SystemTask(generic_models.AbstractTask):

    class Meta(generic_models.AbstractTask.Meta):
        db_table = 'system_task'
        verbose_name = verbose_name_plural = '系统任务'


class ScheduleQueue(generic_models.AbstractTaskScheduleQueue):

    class Meta(generic_models.AbstractTaskScheduleQueue.Meta):
        pass


class ScheduleCallback(generic_models.AbstractScheduleCallback):

    class Meta(generic_models.AbstractScheduleCallback.Meta):
        pass


class SystemSchedule(generic_models.AbstractTaskSchedule):
    task = models.ForeignKey(SystemTask, db_constraint=False, related_name='schedules',
                             on_delete=models.CASCADE, verbose_name='任务')
    callback = models.ForeignKey(ScheduleCallback, on_delete=models.CASCADE,
                                 null=True, blank=True, db_constraint=False, verbose_name='回调')

    class Meta(generic_models.AbstractTaskSchedule.Meta):
        db_table = 'system_schedule'
        verbose_name = verbose_name_plural = '系统计划'
        ordering = ('-update_time',)


class SystemScheduleLog(generic_models.AbstractTaskScheduleLog):
    schedule = models.ForeignKey(SystemSchedule, db_constraint=False, related_name='logs',
                                 on_delete=models.CASCADE, verbose_name='任务计划')

    class Meta(generic_models.AbstractTaskScheduleLog.Meta):
        db_table = 'system_schedule_log'
        verbose_name = verbose_name_plural = '系统日志'
        ordering = ('-schedule_time',)


class ScheduleProducer(generic_models.AbstractTaskScheduleProducer):
    queue = models.ForeignKey(ScheduleQueue, db_constraint=False, related_name='producers',
                              on_delete=models.CASCADE, verbose_name='队列')

    class Meta(generic_models.AbstractTaskScheduleProducer.Meta):
        pass


class ScheduleConsumerPermission(generic_models.AbstractConsumerPermission):
    producer = models.ForeignKey(ScheduleProducer, db_constraint=False,
                                 on_delete=models.CASCADE, verbose_name='生产者')

    class Meta(generic_models.AbstractConsumerPermission.Meta):
        pass


class ExceptionReport(generic_models.AbstractExceptionReport):
    # 注意Meta默认不会继承，需要手动继承
    class Meta(generic_models.AbstractExceptionReport.Meta):
        pass


class SystemTaskClient(generic_models.TaskClient):
    class Meta:
        managed = False
        verbose_name = verbose_name_plural = '任务客户端'

