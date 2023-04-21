from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django_common_objects.admin import UserAdmin
from django.db.models import Count
from datetime import datetime
from .choices import TaskScheduleType, ScheduleTimingType, ScheduleQueueModule, ConsumerPermissionType
from . import models, forms, get_task_model, get_schedule_log_model

TaskModel = get_task_model()
TaskScheduleLogModel = get_schedule_log_model()


class TaskAdmin(UserAdmin):
    schedule_model = models.TaskSchedule

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
            return format_html('<a href="/admin/%s/%s/%s/change/">%s</a>' % (
                obj._meta.app_label, self.model._meta.model_name, obj.parent.id, obj.parent
            ))
        return '-'

    admin_parent.short_description = '父任务'

    def admin_status(self, obj):
        return bool(obj.status)

    admin_status.boolean = True
    admin_status.short_description = '状态'

    def schedules(self, obj):
        schedules = self.extra_context['schedules'].get(obj.id, 0)
        if schedules:
            return format_html('<a href="/admin/%s/%s/?task__id__exact=%s">查看(%s)</a>' % (
                obj._meta.app_label, self.schedule_model._meta.model_name, obj.id, schedules
            ))
        return '-'

    schedules.short_description = '任务计划'

    def changelist_view(self, request, extra_context=None):
        queryset = self.get_queryset(request)
        schedules = self.schedule_model.objects.filter(task__in=queryset, ).values('task__id'
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
    task_model = TaskModel
    schedule_log_model = TaskScheduleLogModel
    queues = models.builtins.queues
    schedule_put_name = 'task_schedule_put'
    list_display = ('id', 'admin_task', 'schedule_type', 'schedule_sub_type', 'next_schedule_time',
                    'status', 'put', 'logs', 'update_time')
    change_list_template = 'admin/system_schedule/change_list.html'
    # readonly_fields = ("next_schedule_time", )

    fields = (
        ("task", "status"),
        "nlp_sentence",
        ("schedule_type", 'priority', 'base_on_now'),
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
        return format_html('<a href="/admin/%s/%s/%s/change/">%s</a>' % (
            obj._meta.app_label, self.task_model._meta.model_name, obj.task.id, obj.task.name
        ))
    admin_task.short_description = '任务'

    def logs(self, obj):
        return format_html('<a href="/admin/%s/%s/?schedule__id__exact=%s">查看</a>' % (
            obj._meta.app_label, self.schedule_log_model._meta.model_name, obj.id
        ))
    logs.short_description = '日志'

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

    def get_available_queues(self, obj):
        return self.queues.values()

    def put(self, obj):
        now = datetime.now()
        url = reverse(self.schedule_put_name) + '?i=%s' % obj.id
        templates = '''
            <div style="padding: 10px; border-bottom: 1px solid black">
                <div>
                    <span>计划日期</span>
                    <input type="text" value="%s" class="vDateField">
                </div>
                <span>计划时间</span>
                <input type="text" value="%s" class="vTimeField">
            </div>
        ''' % (now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S'))
        for queue in self.get_available_queues(obj):
            queue_url = url + '&q=%s' % queue.code
            templates += """
                <li>
                    <a href="javascript:void(0);" onclick="put_schedule('%s', %s)"><div>%s</div></a>
                </li>
            """ % (queue_url, obj.id, queue.name,)
        return mark_safe(
            '''
            
                <div class="schedule_box" id="schedule_box_%s">
                    <span class="pop_ctrl" style="padding:5px;border:none;color: var(--secondary)">加入队列</span>
                    <ul>%s</ul>
                </div>
                
            ''' % (obj.id, templates)
        )
    put.allow_tags = True
    put.short_description = '调度'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('task')

    class Media:
        js = (
            'https://cdn.bootcss.com/jquery/3.3.1/jquery.min.js',
            'https://cdn.bootcss.com/popper.js/1.14.3/umd/popper.min.js',
            'https://cdn.bootcss.com/bootstrap/4.1.3/js/bootstrap.min.js',
            # reverse('admin:jsi18n'),
            'common_task_system/js/task_schedule_admin.js',
            'common_task_system/js/calendar.js',
            'admin/js/calendar.js',
            'admin/js/admin/DateTimeShortcuts.js'
        )
        css = {
            'all': (
                'common_task_system/css/task_schedule_admin.css',
                'admin/css/base.css',
                'admin/css/forms.css',
            )
        }


class TaskScheduleLogAdmin(UserAdmin):
    schedule_retry_name = 'task_schedule_retry'
    list_display = ('id', 'schedule', 'status', 'retry', 'schedule_time', 'create_time')

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def retry(self, obj):
        url = reverse(self.schedule_retry_name) + '?log-ids=%s' % obj.id
        return format_html(
            '<a href="%s" target="_blank">重试</a>' % url
        )
    retry.allow_tags = True
    retry.short_description = '重试'


class TaskScheduleQueueAdmin(admin.ModelAdmin):
    form = forms.TaskScheduleQueueForm
    builtins = models.builtins
    schedule_get_name = 'task_schedule_get'

    list_display = ('id', 'name', 'code', 'queue_url', 'module', 'status', 'queue_size', 'update_time')

    fields = (
        ('code', 'module', 'status'),
        'name',
        'config'
    )

    def queue_size(self, obj):
        q = self.builtins.queues.get(obj.code, None)
        if q:
            return q.queue.qsize()
        return 0
    queue_size.short_description = '队列大小'

    def queue_url(self, obj):
        url = reverse(self.schedule_get_name, args=(obj.code,))
        return format_html(
            '<a href="%s" target="_blank">%s</a>' % (url, url)
        )
    queue_url.short_description = '队列地址'


class TaskScheduleProducerAdmin(admin.ModelAdmin):
    form = forms.TaskScheduleProducerForm
    builtins = models.builtins
    schedule_get_name = 'task_schedule_get'
    list_display = ('id', 'name', 'producer_queue', 'consumer_url', 'task_num', 'status', 'update_time')

    fields = (
        ('name', 'status', 'lte_now'),
        'queue',
        'filters',
    )

    def producer_queue(self, obj):
        for i in ScheduleQueueModule:
            i: ScheduleQueueModule
            if i.value == obj.queue.module:
                return '%s(%s)-%s' % (obj.queue.name, obj.queue.code, i.label)
        return '%s(%s)' % (obj.queue.name, obj.queue.code)
    producer_queue.short_description = '生产队列'

    def consumer_url(self, obj):
        url = reverse(self.schedule_get_name, args=(obj.queue.code,))
        return format_html(
            '<a href="%s" target="_blank">%s</a>' % (url, url)
        )
    consumer_url.short_description = '消费地址'

    def task_num(self, obj):
        q = self.builtins.queues.get(obj.queue.code, None)
        if q:
            return q.queue.qsize()
        return 0
    task_num.short_description = '任务数量'


class ConsumerPermissionAdmin(admin.ModelAdmin):
    form = forms.ConsumerPermissionForm
    list_display = ('id', 'producer', 'type', 'summary', 'status', 'update_time')

    fields = (
        ('producer', 'status'),
        'type',
        'ip_whitelist',
        'config'
    )

    def summary(self, obj):
        if obj.type == ConsumerPermissionType.IP_WHITE_LIST:
            return obj.config['ip_whitelist'][0:5]
        return '-'
    summary.short_description = '摘要'


class ExceptionReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'ip', 'content', 'create_time')

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


admin.site.register(TaskModel, TaskAdmin)
admin.site.register(models.TaskSchedule, TaskScheduleAdmin)
admin.site.register(models.TaskScheduleCallback, TaskScheduleCallbackAdmin)
admin.site.register(TaskScheduleLogModel, TaskScheduleLogAdmin)
admin.site.register(models.TaskScheduleQueue, TaskScheduleQueueAdmin)
admin.site.register(models.TaskScheduleProducer, TaskScheduleProducerAdmin)
admin.site.register(models.ConsumerPermission, ConsumerPermissionAdmin)
admin.site.register(models.ExceptionReport, ExceptionReportAdmin)

