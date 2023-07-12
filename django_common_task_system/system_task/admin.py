from django.contrib import admin
from . import models
from .builtins import builtins
from . import forms
from django_common_task_system.generic import admin as generic_admin
from django_common_task_system.generic.client import TaskClient


class SystemTaskAdmin(generic_admin.TaskAdmin):
    form = forms.SystemTaskForm
    schedule_model = models.SystemSchedule

    fields = (
        'category',
        ("name", "status",),
        ("parent", 'queue', 'include_meta'),
        ('custom_program', ),
        'sql_config',
        "script",
        "config",
        'description',
    )
    filter_horizontal = []
    list_filter = (generic_admin.CategoryFilter.of_model(model=models.SystemTask), 'tags', 'status', 'parent')

    def has_delete_permission(self, request, obj=None):
        if obj and not request.user.is_superuser:
            return obj.category != builtins.categories.system_default_category
        return True

    class Media:
        js = (
            'https://cdn.bootcss.com/jquery/3.3.1/jquery.min.js',
            'https://cdn.bootcss.com/popper.js/1.14.3/umd/popper.min.js',
            'https://cdn.bootcss.com/bootstrap/4.1.3/js/bootstrap.min.js',
            'common_task_system/js/task_type_admin.js',
        )


class SystemScheduleCallbackAdmin(generic_admin.TaskScheduleCallbackAdmin):
    pass


class SystemScheduleAdmin(generic_admin.TaskScheduleAdmin):
    task_model = models.SystemTask
    schedule_log_model = models.SystemScheduleLog
    queues = builtins.queues
    schedule_put_name = 'system_schedule_put'
    list_filter = ('task__category', 'status')

    def has_delete_permission(self, request, obj=None):
        if obj and not request.user.is_superuser:
            return obj.task.category != builtins.categories.system_default_category
        return True


class SystemScheduleLogAdmin(generic_admin.TaskScheduleLogAdmin):
    schedule_retry_name = 'system_schedule_retry'


class SystemScheduleQueueAdmin(generic_admin.TaskScheduleQueueAdmin):
    form = forms.SystemScheduleQueueForm
    builtins = builtins
    schedule_get_name = 'system_schedule_get'


class SystemScheduleProducerAdmin(generic_admin.TaskScheduleProducerAdmin):
    form = forms.SystemScheduleProducerForm
    schedule_get_name = 'system_schedule_get'
    builtins = builtins


admin.site.register(models.SystemTask, SystemTaskAdmin)
admin.site.register(models.SystemScheduleCallback, SystemScheduleCallbackAdmin)
admin.site.register(models.SystemSchedule, SystemScheduleAdmin)
admin.site.register(models.SystemScheduleLog, SystemScheduleLogAdmin)
admin.site.register(models.SystemScheduleQueue, SystemScheduleQueueAdmin)
admin.site.register(models.SystemScheduleProducer, SystemScheduleProducerAdmin)
admin.site.register(TaskClient, generic_admin.TaskClientAdmin)
admin.site.register(models.SystemConsumerPermission, generic_admin.ConsumerPermissionAdmin)
admin.site.register(models.SystemExceptionReport, generic_admin.ExceptionReportAdmin)
