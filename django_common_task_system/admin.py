from django.contrib import admin
from django_common_task_system.generic import admin as generic_admin
from django_common_task_system.generic import models as generic_models
from . import models, forms, get_task_model, get_schedule_log_model, get_task_schedule_model
from .builtins import builtins

TaskModel = get_task_model()
ScheduleModel = get_task_schedule_model()
TaskScheduleLogModel = get_schedule_log_model()


class TaskAdmin(generic_admin.TaskAdmin):
    schedule_model = ScheduleModel
    form = forms.TaskForm
    list_filter = (generic_admin.CategoryFilter.of_model(model=TaskModel), 'tags', 'parent')


class TaskScheduleAdmin(generic_admin.TaskScheduleAdmin):
    task_model = TaskModel
    schedule_log_model = TaskScheduleLogModel
    queues = builtins.queues
    schedule_put_name = 'user-schedule-put'
    form = forms.TaskScheduleForm


class TaskScheduleLogAdmin(generic_admin.TaskScheduleLogAdmin):
    schedule_retry_name = 'user-schedule-retry'


class TaskScheduleQueueAdmin(generic_admin.TaskScheduleQueueAdmin):
    form = forms.TaskScheduleQueueForm
    builtins = builtins
    schedule_get_name = 'user-schedule-get'


class TaskScheduleProducerAdmin(generic_admin.TaskScheduleProducerAdmin):
    form = forms.TaskScheduleProducerForm
    builtins = builtins
    schedule_get_name = 'user-schedule-get'


class CustomTaskClient(generic_models.TaskClient):

    class Meta:
        proxy = True
        verbose_name = verbose_name_plural = '任务客户端'


admin.site.register(TaskModel, TaskAdmin)
admin.site.register(ScheduleModel, TaskScheduleAdmin)
admin.site.register(models.TaskScheduleCallback, generic_admin.TaskScheduleCallbackAdmin)
admin.site.register(TaskScheduleLogModel, TaskScheduleLogAdmin)
admin.site.register(models.TaskScheduleQueue, TaskScheduleQueueAdmin)
admin.site.register(models.TaskScheduleProducer, TaskScheduleProducerAdmin)
admin.site.register(models.ConsumerPermission, generic_admin.ConsumerPermissionAdmin)
admin.site.register(models.ExceptionReport, generic_admin.ExceptionReportAdmin)
admin.site.register(CustomTaskClient, generic_admin.TaskClientAdmin)


admin.site.site_header = '任务管理系统'
admin.site.site_title = '任务管理系统'
