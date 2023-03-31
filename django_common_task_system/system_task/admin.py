from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.db.models import Count
from . import models
from . import forms
from .. import admin as base_admin


class SystemTaskAdmin(base_admin.TaskAdmin):
    form = forms.SystemTaskForm
    schedule_model = models.SystemSchedule

    fields = (
        ("parent", 'category',),
        ('task_type', 'queue',),
        ("name", "status",),
        "config",
        'description',
    )
    filter_horizontal = []
    list_filter = ('category', 'parent')


class SystemScheduleAdmin(base_admin.TaskScheduleAdmin):

    task_model = models.SystemTask
    schedule_log_model = models.SystemScheduleLog


class SystemScheduleLogAdmin(base_admin.TaskScheduleLogAdmin):
    pass


class SystemScheduleQueueAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'code', 'update_time')


admin.site.register(models.SystemTask, SystemTaskAdmin)
admin.site.register(models.SystemSchedule, SystemScheduleAdmin)
admin.site.register(models.SystemScheduleLog, SystemScheduleLogAdmin)
admin.site.register(models.SystemScheduleQueue, SystemScheduleQueueAdmin)

