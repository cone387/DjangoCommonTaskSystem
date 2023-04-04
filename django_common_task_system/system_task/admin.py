from django.contrib import admin
import subprocess
from django.shortcuts import reverse
from django.utils.html import format_html
from . import models
from . import forms
from .. import admin as base_admin
from .choices import SystemTaskType


class SystemTaskAdmin(base_admin.TaskAdmin):
    form = forms.SystemTaskForm
    schedule_model = models.SystemSchedule
    list_display = ('id', 'task_type', 'admin_parent', 'name', 'category', 'admin_status', 'schedules', 'update_time')

    fields = (
        ("parent", 'category',),
        ('task_type', 'queue',),
        ("name", "status",),
        "config",
        'description',
    )
    filter_horizontal = []
    list_filter = ('task_type', 'category', 'parent')


class SystemScheduleAdmin(base_admin.TaskScheduleAdmin):

    task_model = models.SystemTask
    schedule_log_model = models.SystemScheduleLog

    list_display = ('id', 'task_type', 'admin_task', 'schedule_type', 'schedule_sub_type', 'next_schedule_time',
                    'status', 'put', 'logs', 'update_time')

    def task_type(self, obj):
        return SystemTaskType[obj.task.task_type].label
    task_type.short_description = '任务类型'

    def put(self, obj):
        url = reverse('system_schedule_queue_put', args=(obj.id,))
        return format_html(
            '<a href="%s" target="_blank">调度+1</a>' % url
        )
    put.allow_tags = True
    put.short_description = '调度'

    def has_delete_permission(self, request, obj=None):
        if obj:
            return False
        return True


class SystemScheduleLogAdmin(base_admin.TaskScheduleLogAdmin):

    def retry(self, obj):
        url = reverse('system_schedule_retry', args=(obj.id,))
        return format_html(
            '<a href="%s" target="_blank">重试</a>' % url
        )

    retry.allow_tags = True
    retry.short_description = '重试'


class SystemScheduleQueueAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'code', 'queue_url', 'module', 'update_time')

    fields = (
        ('code', 'module', 'status'),
        'name',
    )

    def queue_url(self, obj):
        url = reverse('system_schedule_queue_get', args=(obj.code,))
        return format_html(
            '<a href="%s" target="_blank">%s</a>' % (url, url)
        )
    queue_url.allow_tags = True
    queue_url.short_description = '队列地址'


class SystemProcessAdmin(admin.ModelAdmin):
    list_display = ('container_id', 'container_name', 'env', 'create_time', 'update_time')

    fields = (
        'env',
    )

    def get_queryset(self, request):
        p = subprocess.Popen('docker ps -a --filter "name=report" --format "{{.ID}} {{.Names}}"',
                             shell=True, stdout=subprocess.PIPE)
        out, err = p.communicate()
        if err:
            return super().get_queryset(request)
        out = out.decode('utf-8')
        for line in out.splitlines():
            container_id, container_name = line.split(' ')
            obj, _ = models.SystemProcess.objects.get_or_create(container_id=container_id.strip(),
                                                                container_name=container_name.strip())
        return super().get_queryset(request)


admin.site.register(models.SystemTask, SystemTaskAdmin)
admin.site.register(models.SystemSchedule, SystemScheduleAdmin)
admin.site.register(models.SystemScheduleLog, SystemScheduleLogAdmin)
admin.site.register(models.SystemScheduleQueue, SystemScheduleQueueAdmin)
admin.site.register(models.SystemProcess, SystemProcessAdmin)

