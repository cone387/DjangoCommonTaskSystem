from django.contrib import admin
from django.utils.html import format_html
from .choices import TaskScheduleType
from django_common_objects.admin import UserAdmin
from django.db.models import Count
from . import models, forms


class TaskAdmin(UserAdmin):
    form = forms.TaskForm
    list_display = ('id', 'admin_parent', 'name', 'category', 'admin_status', 'schedules', 'update_time')
    fields = (
        ("parent", 'category',),
        ("name", "status",),
        "config",
        "tags",
        'description',

    )
    filter_horizontal = ('tags',)
    list_filter = ('category', 'tags', 'parent')

    def __init__(self, *args, **kwargs):
        super(TaskAdmin, self).__init__(*args, **kwargs)
        self.extra_context = {'schedules': {}}

    def admin_parent(self, obj):
        if obj.parent:
            return format_html('<a href="/admin/task_schedule/task/%s/change/">%s</a>' % (obj.parent.id, obj.parent))
        return '-'

    admin_parent.short_description = '父任务'

    def admin_status(self, obj):
        return bool(obj.status)

    admin_status.boolean = True
    admin_status.short_description = '状态'

    def schedules(self, obj):
        schedules = self.extra_context['schedules'].get(obj.id, 0)
        if schedules:
            return format_html('<a href="/admin/task_schedule/taskschedule/?task__id__exact=%s">查看(%s)</a>'
                               % (obj.id, schedules))
        return '-'

    schedules.short_description = '任务计划'

    def changelist_view(self, request, extra_context=None):
        queryset = self.get_queryset(request)
        schedules = models.TaskSchedule.objects.filter(task__in=queryset, ).values('task__id'
                                                                                   ).annotate(Count('task__id'))
        self.extra_context['schedules'] = {x['task__id']: x['task__id__count'] for x in schedules}
        return super(TaskAdmin, self).changelist_view(request, extra_context=self.extra_context)


class TaskScheduleCallbackAdmin(UserAdmin):
    list_display = ('id', 'name', 'status', 'user', 'update_time')
    fields = (
        "name",
        ("trigger_event", "status",),
        "config",
        'description',

    )


class TaskScheduleAdmin(UserAdmin):
    list_display = ('id', 'admin_task', 'type', 'crontab', 'next_schedule_time',
                    'admin_period', 'admin_status', 'logs', 'update_time')
    fields = (
        ("task", "status"),
        ("type", 'priority'),
        'crontab',
        ("next_schedule_time", 'period'),
        'callback'
    )
    form = forms.TaskScheduleForm

    def admin_task(self, obj):
        return format_html('<a href="/admin/task_schedule/task/%s/change/">%s</a>' % (obj.task.id, obj.task.name))

    admin_task.short_description = '任务'

    def logs(self, obj):
        return format_html('<a href="/admin/task_schedule/taskschedulelog/?schedule__id__exact=%s">查看</a>' % obj.id)

    logs.short_description = '日志'

    def admin_status(self, obj):
        return bool(obj.status)

    admin_status.boolean = True
    admin_status.short_description = '状态'

    def admin_period(self, obj):
        if obj.type != TaskScheduleType.CONTINUOUS:
            return '-'
        return obj.period

    admin_period.short_description = '周期'

    class Media:
        js = (
            'https://cdn.bootcss.com/jquery/3.3.1/jquery.min.js',
            'https://cdn.bootcss.com/popper.js/1.14.3/umd/popper.min.js',
            'https://cdn.bootcss.com/bootstrap/4.1.3/js/bootstrap.min.js',
            # reverse('admin:jsi18n'),
            # 'js/task_schedule_admin.js',
            'common_task_system/js/task_schedule_admin.js'
        )


class TaskScheduleLogAdmin(UserAdmin):
    list_display = ('id', 'schedule', 'schedule_time', 'finish_time')

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


admin.site.register(models.Task, TaskAdmin)
admin.site.register(models.TaskSchedule, TaskScheduleAdmin)
admin.site.register(models.TaskScheduleCallback, TaskScheduleCallbackAdmin)
admin.site.register(models.TaskScheduleLog, TaskScheduleLogAdmin)
