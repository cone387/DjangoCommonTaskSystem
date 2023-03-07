from django.contrib import admin
from django.utils.html import format_html
from django_common_objects.admin import UserAdmin
from django.db.models import Count
from .choices import TaskScheduleType, ScheduleTimingType
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
    list_display = ('id', 'admin_task', 'schedule_type', 'schedule_sub_type', 'next_schedule_time',
                    'admin_status', 'logs', 'update_time')

    # readonly_fields = ("next_schedule_time", )

    fields = (
        ("task", "status"),
        "nlp_sentence",
        ("schedule_type", 'priority'),
        "period_schedule",
        "once_schedule",
        "crontab",
        "timing_type",
        "timing_weekday",
        "timing_monthday",
        "timing_year",
        ("timing_period", "timing_time",),
        "timing_datetime",
        ("schedule_start_time", "schedule_end_time"),
        'callback',
        'next_schedule_time',
        'config',
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

    def schedule_type(self, obj):
        t = obj.config.get("schedule_type")
        for i in TaskScheduleType:
            i: TaskScheduleType
            if i == t:
                return i.label
        return '-'

    schedule_type.short_description = '计划类型'

    def schedule_sub_type(self, obj: models.TaskSchedule):
        config = obj.config
        schedule_type = config.get("schedule_type", "-")
        type_config = config.get(schedule_type, {})
        if schedule_type == TaskScheduleType.CRONTAB:
            return type_config.get('crontab', '')
        elif schedule_type == TaskScheduleType.CONTINUOUS:
            return "每%s秒" % type_config.get('period', '')
        elif schedule_type == TaskScheduleType.TIMINGS:
            return ScheduleTimingType[config[schedule_type]['type']].label
        return '-'

    schedule_sub_type.short_description = '详细'

    class Media:
        js = (
            'https://cdn.bootcss.com/jquery/3.3.1/jquery.min.js',
            'https://cdn.bootcss.com/popper.js/1.14.3/umd/popper.min.js',
            'https://cdn.bootcss.com/bootstrap/4.1.3/js/bootstrap.min.js',
            # reverse('admin:jsi18n'),
            'common_task_system/js/task_schedule_admin.js',
        )
        css = {
            'all': (
                'common_task_system/css/task_schedule_admin.css',
            )
        }


class TaskScheduleLogAdmin(UserAdmin):
    list_display = ('id', 'schedule', 'schedule_time', 'finish_time')

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


admin.site.register(models.Task, TaskAdmin)
admin.site.register(models.TaskSchedule, TaskScheduleAdmin)
admin.site.register(models.TaskScheduleCallback, TaskScheduleCallbackAdmin)
admin.site.register(models.TaskScheduleLog, TaskScheduleLogAdmin)
