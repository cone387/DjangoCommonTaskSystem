from django.contrib.auth import get_user_model
from django.db import models
from django_common_task_system.generic import models as generic_models


UserModel = get_user_model()


class Task(generic_models.AbstractTask):

    class Meta(generic_models.AbstractTask.Meta):
        db_table = 'taskhub'
        swappable = 'TASK_MODEL'


class TaskScheduleCallback(generic_models.AbstractScheduleCallback):

    class Meta(generic_models.AbstractScheduleCallback.Meta):
        db_table = 'task_schedule_callback'


class TaskSchedule(generic_models.AbstractTaskSchedule):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, db_constraint=False, verbose_name='任务')
    callback = models.ForeignKey(TaskScheduleCallback, on_delete=models.CASCADE,
                                 null=True, blank=True, db_constraint=False, verbose_name='回调')

    class Meta(generic_models.AbstractTaskSchedule.Meta):
        swappable = 'TASK_SCHEDULE_MODEL'
        db_table = 'task_schedule'


class TaskScheduleQueue(generic_models.AbstractTaskScheduleQueue):
    class Meta(generic_models.AbstractTaskScheduleQueue.Meta):
        db_table = 'task_schedule_queue'


class TaskScheduleProducer(generic_models.AbstractTaskScheduleProducer):
    queue = models.ForeignKey(TaskScheduleQueue, db_constraint=False, related_name='producers',
                              on_delete=models.CASCADE, verbose_name='队列')

    class Meta(generic_models.AbstractTaskScheduleProducer.Meta):
        db_table = 'task_schedule_producer'


class TaskScheduleLog(generic_models.AbstractTaskScheduleLog):
    schedule = models.ForeignKey(TaskSchedule, db_constraint=False, related_name='logs',
                                 on_delete=models.CASCADE, verbose_name='任务计划')

    class Meta(generic_models.AbstractTaskScheduleLog.Meta):
        swappable = 'TASK_SCHEDULE_LOG_MODEL'
        db_table = 'task_schedule_log'


class ConsumerPermission(generic_models.AbstractConsumerPermission):
    producer = models.ForeignKey(TaskScheduleProducer, db_constraint=False,
                                 on_delete=models.CASCADE, verbose_name='生产者')

    class Meta(generic_models.AbstractConsumerPermission.Meta):
        db_table = 'schedule_consumer_permission'


class ExceptionReport(generic_models.AbstractExceptionReport):
    class Meta(generic_models.AbstractExceptionReport.Meta):
        db_table = 'task_exception_report'
