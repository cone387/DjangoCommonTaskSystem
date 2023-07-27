from django.contrib import admin
from django_common_task_system.generic import admin as generic_admin
from django_common_task_system.generic import models as generic_models
from . import models, forms, get_user_task_model, get_schedule_log_model, get_user_schedule_model
from .builtins import builtins

UserTaskModel = get_user_task_model()
UserScheduleModel = get_user_schedule_model()
UserScheduleLogModel = get_schedule_log_model()


class TaskAdmin(generic_admin.TaskAdmin):
    schedule_model = UserScheduleModel
    form = forms.TaskForm
    list_filter = (generic_admin.CategoryFilter.of_model(model=UserTaskModel), 'tags', 'parent')


class ScheduleAdmin(generic_admin.ScheduleAdmin):
    task_model = UserTaskModel
    schedule_log_model = UserScheduleLogModel
    queues = builtins.queues
    schedule_put_name = 'user-schedule-put'
    form = forms.TaskScheduleForm


class ScheduleLogAdmin(generic_admin.ScheduleLogAdmin):
    schedule_retry_name = 'user-schedule-retry'


class ScheduleQueueAdmin(generic_admin.ScheduleQueueAdmin):
    form = forms.TaskScheduleQueueForm
    builtins = builtins
    schedule_get_name = 'user-schedule-get'


class ScheduleProducerAdmin(generic_admin.ScheduleProducerAdmin):
    form = forms.ScheduleProducerForm
    builtins = builtins
    schedule_get_name = 'user-schedule-get'


admin.site.register(UserTaskModel, TaskAdmin)
admin.site.register(UserScheduleModel, ScheduleAdmin)
admin.site.register(models.ScheduleCallback, generic_admin.ScheduleCallbackAdmin)
admin.site.register(UserScheduleLogModel, ScheduleLogAdmin)
admin.site.register(models.ScheduleQueue, ScheduleQueueAdmin)
admin.site.register(models.ScheduleProducer, ScheduleProducerAdmin)
admin.site.register(models.ScheduleConsumerPermission, generic_admin.ConsumerPermissionAdmin)
admin.site.register(models.ExceptionReport, generic_admin.ExceptionReportAdmin)
admin.site.register(models.UserTaskClient, generic_admin.TaskClientAdmin)


admin.site.site_header = '任务管理系统'
admin.site.site_title = '任务管理系统'
