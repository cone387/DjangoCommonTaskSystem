from django.contrib.auth import get_user_model
from django.db import models
from django_common_task_system.generic import models as generic_models
from django_common_task_system.generic.app import App
from django.conf import settings
import os


UserModel = get_user_model()


if App.system_task.is_installed:
    from django_common_task_system.system_task import models as system_models

    class ExceptionReport(system_models.ExceptionReport):
        class Meta(system_models.ExceptionReport.Meta):
            proxy = True


    class ScheduleCallback(system_models.ScheduleCallback):

        class Meta(system_models.ScheduleCallback.Meta):
            proxy = True


    class ScheduleQueue(system_models.ScheduleQueue):

        class Meta(system_models.ScheduleQueue.Meta):
            proxy = True


    class ScheduleProducer(system_models.ScheduleProducer):

        class Meta(system_models.ScheduleProducer.Meta):
            proxy = True


    class ScheduleConsumerPermission(system_models.ScheduleConsumerPermission):

        class Meta(system_models.ScheduleConsumerPermission.Meta):
            proxy = True


    class UserTaskClient(system_models.SystemTaskClient):

        class Meta:
            proxy = True
            verbose_name = verbose_name_plural = '任务客户端'

else:
    class ExceptionReport(generic_models.AbstractExceptionReport):
        class Meta(generic_models.AbstractExceptionReport.Meta):
            pass

    class ScheduleCallback(generic_models.AbstractScheduleCallback):

        class Meta(generic_models.AbstractScheduleCallback.Meta):
            pass

    class ScheduleQueue(generic_models.AbstractTaskScheduleQueue):

        class Meta(generic_models.AbstractTaskScheduleQueue.Meta):
            pass

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


    class UserTaskClient(generic_models.TaskClient):

        class Meta:
            managed = False
            verbose_name = verbose_name_plural = '任务客户端'


class UserTask(generic_models.AbstractTask):

    class Meta(generic_models.AbstractTask.Meta):
        db_table = 'user_task'
        swappable = 'USER_TASK_MODEL'


class UserSchedule(generic_models.AbstractTaskSchedule):
    task = models.ForeignKey(settings.USER_TASK_MODEL, on_delete=models.CASCADE, db_constraint=False, verbose_name='任务')
    callback = models.ForeignKey(ScheduleCallback, on_delete=models.CASCADE,
                                 null=True, blank=True, db_constraint=False, verbose_name='回调')

    class Meta(generic_models.AbstractTaskSchedule.Meta):
        swappable = 'USER_SCHEDULE_MODEL'
        db_table = 'user_schedule'


class UserScheduleLog(generic_models.AbstractTaskScheduleLog):
    schedule = models.ForeignKey(settings.USER_SCHEDULE_MODEL, db_constraint=False, related_name='logs',
                                 on_delete=models.CASCADE, verbose_name='任务计划')

    class Meta(generic_models.AbstractTaskScheduleLog.Meta):
        swappable = 'USER_SCHEDULE_LOG_MODEL'
        db_table = 'user_schedule_log'

