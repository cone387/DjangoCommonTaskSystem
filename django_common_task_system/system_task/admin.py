from django.contrib import admin
from django.dispatch import receiver
from django.shortcuts import reverse
from django.utils.html import format_html
from django.db.models.signals import post_delete
from . import models
from . import forms
from .. import admin as base_admin
from .process import ProcessManager
from ..system_task_execution.main import start_system_client
import os


def init_system_process():
    logs_path = os.path.join(os.getcwd(), 'logs')
    if not os.path.exists(logs_path):
        os.mkdir(logs_path)
    models.SystemProcess.objects.all().delete()
    name = 'system-process-default'
    log_file = os.path.join(logs_path, f'{name}.log')
    instance = models.SystemProcess(
        process_name=name,
        log_file=log_file
    )
    process = ProcessManager.create(start_system_client, instance.log_file)
    instance.process_id = process.pid
    instance.save()


def init_system_data():
    from .models import builtins
    builtins.initialize()


if os.environ.get('RUN_MAIN') == 'true' and os.environ.get('RUN_CLIENT') != 'true':
    init_system_process()
    init_system_data()


@receiver(post_delete, sender=models.SystemProcess)
def delete_process(sender, instance: models.SystemProcess, **kwargs):
    ProcessManager.kill(instance.process_id)
    if os.path.isfile(instance.log_file) and not instance.log_file.endswith('system-process-default.log'):
        os.remove(instance.log_file)


class SystemTaskAdmin(base_admin.TaskAdmin):
    form = forms.SystemTaskForm
    schedule_model = models.SystemSchedule
    list_display = ('id', 'admin_parent', 'name', 'category', 'admin_status', 'schedules', 'update_time')

    fields = (
        ("parent", 'category',),
        ('queue',),
        ("name", "status",),
        "config",
        'description',
    )
    filter_horizontal = []
    list_filter = ('category', 'parent')

    def has_delete_permission(self, request, obj=None):
        if obj:
            return obj.category != models.builtins.categories.system_default_category
        return True


class SystemScheduleCallbackAdmin(base_admin.TaskScheduleCallbackAdmin):
    pass


class SystemScheduleAdmin(base_admin.TaskScheduleAdmin):

    task_model = models.SystemTask
    schedule_log_model = models.SystemScheduleLog
    queues = models.builtins.queues
    schedule_put_name = 'system_schedule_put'
    list_display = ('id', 'admin_task', 'schedule_type', 'schedule_sub_type', 'next_schedule_time',
                    'status', 'put', 'logs', 'update_time')
    list_filter = ('task__category', )

    def has_delete_permission(self, request, obj=None):
        if obj:
            return obj.task.category != models.builtins.categories.system_default_category
        return True


class SystemScheduleLogAdmin(base_admin.TaskScheduleLogAdmin):
    schedule_retry_name = 'system_schedule_retry'


class SystemProcessAdmin(admin.ModelAdmin):
    list_display = ('process_id', 'process_name', 'log_file', 'status', 'stop_process', 'show_log', 'update_time')
    form = forms.SystemProcessForm
    fields = (
        'system_path',
        'process_name',
        'env',
        'log_file',
        'process_id',
        'create_time',
    )

    readonly_fields = ('create_time', 'update_time')

    def stop_process(self, obj):
        url = reverse('system_process_stop', args=(obj.process_id,))
        return format_html(
            '<a href="%s" target="_blank">停止</a>' % url
        )
    stop_process.short_description = '停止运行'

    def show_log(self, obj):
        url = reverse('system_process_log', args=(obj.process_id,))
        return format_html(
            '<a href="%s" target="_blank">查看日志</a>' % url
        )
    show_log.short_description = '日志'

    def has_delete_permission(self, request, obj=None):
        return False


class SystemScheduleQueueAdmin(base_admin.TaskScheduleQueueAdmin):
    form = forms.SystemScheduleQueueForm
    builtins = models.builtins
    schedule_get_name = 'system_schedule_get'


class SystemScheduleProducerAdmin(base_admin.TaskScheduleProducerAdmin):
    form = forms.SystemScheduleProducerForm
    schedule_get_name = 'system_schedule_get'
    builtins = models.builtins


class SystemConsumerPermissionAdmin(base_admin.ConsumerPermissionAdmin):
    pass


class SystemExceptionAdmin(base_admin.ExceptionReportAdmin):
    pass


admin.site.register(models.SystemTask, SystemTaskAdmin)
admin.site.register(models.SystemScheduleCallback, SystemScheduleCallbackAdmin)
admin.site.register(models.SystemSchedule, SystemScheduleAdmin)
admin.site.register(models.SystemScheduleLog, SystemScheduleLogAdmin)
admin.site.register(models.SystemScheduleQueue, SystemScheduleQueueAdmin)
admin.site.register(models.SystemScheduleProducer, SystemScheduleProducerAdmin)
admin.site.register(models.SystemProcess, SystemProcessAdmin)
admin.site.register(models.SystemConsumerPermission, SystemConsumerPermissionAdmin)
admin.site.register(models.SystemExceptionReport, SystemExceptionAdmin)

