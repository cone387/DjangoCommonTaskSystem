from django.contrib import admin, messages
from django.urls import reverse, Resolver404
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django_common_objects.admin import UserAdmin
from django.db.models import Count
from datetime import datetime
from django_common_objects.models import CommonCategory
from . import forms
from .choices import TaskScheduleType, ScheduleTimingType, ScheduleQueueModule, ConsumerPermissionType, TaskClientStatus
from .models import TaskClient
from docker.errors import APIError
from django.urls import resolve
import docker
from urllib.parse import urlparse


class CategoryFilter(admin.SimpleListFilter):
    title = '任务分类'
    parameter_name = 'category'

    def lookups(self, request, model_admin):
        model = getattr(self, 'model')
        return CommonCategory.objects.filter(model=model._meta.label).values_list('id', 'name')

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(category_id=self.value())
        return queryset

    @classmethod
    def of_model(cls, model):
        return type('%sCategoryFilter' % model.__name__, (cls,), {'model': model})


class TaskAdmin(UserAdmin):
    schedule_model = None
    list_display = ('id', 'admin_parent', 'name', 'category', 'admin_status', 'schedules', 'update_time')
    fields = (
        ("parent", 'category',),
        ("name", "status",),
        "config",
        "tags",
        'description',

    )
    filter_horizontal = ('tags',)

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
        return format_html('<a href="/admin/%s/%s/add/?task=%s">创建计划</a>' % (
            obj._meta.app_label, self.schedule_model._meta.model_name, obj.id
        ))

    schedules.short_description = '任务计划'

    def changelist_view(self, request, extra_context=None):
        queryset = self.get_queryset(request)
        schedules = self.schedule_model.objects.filter(task__in=queryset, ).values('task__id'
                                                                                   ).annotate(Count('task__id'))
        self.extra_context['schedules'] = {x['task__id']: x['task__id__count'] for x in schedules}
        return super(TaskAdmin, self).changelist_view(request, extra_context=self.extra_context)


class ScheduleCallbackAdmin(UserAdmin):
    list_display = ('id', 'name', 'status', 'user', 'update_time')
    fields = (
        "name",
        ("trigger_event", "status",),
        "config",
        'description',

    )


class ScheduleAdmin(UserAdmin):
    task_model = None
    schedule_log_model = None
    queues = None
    schedule_put_name = 'user-schedule-put'
    list_display = ('id', 'admin_task', 'schedule_type', 'schedule_sub_type', 'next_schedule_time',
                    'status', 'strict', 'put', 'logs', 'update_time')
    change_list_template = ['admin/system_schedule/change_list.html']
    # readonly_fields = ("next_schedule_time", )
    form = forms.ScheduleForm

    fields = (
        ("task", "status"),
        "nlp_sentence",
        ("schedule_type", 'priority', 'base_on_now', 'strict_mode'),
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

    def strict(self, obj):
        return '是' if obj.strict_mode else '否'
    strict.boolean = False
    strict.short_description = '严格模式'

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

    def schedule_sub_type(self, obj):
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


class ScheduleLogAdmin(UserAdmin):
    schedule_retry_name = None
    list_display = ('id', 'schedule', 'status', 'retry', 'schedule_time', 'create_time')
    list_filter = ('status', 'schedule')

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def retry(self, obj):
        url = reverse(self.schedule_retry_name) + '?log-ids=%s' % obj.id
        return format_html(
            '<a href="%s" target="_blank">重试</a>' % url
        )

    retry.allow_tags = True
    retry.short_description = '重试'


class ScheduleQueueAdmin(admin.ModelAdmin):
    builtins = None
    schedule_get_name = 'user-schedule-get'

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


class ScheduleProducerAdmin(admin.ModelAdmin):
    builtins = None
    schedule_get_name = 'user-schedule-get'
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
    list_display = ('id', 'producer', 'type', 'summary', 'status', 'update_time')
    form = forms.ConsumerPermissionForm
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
    list_display = ('id', 'group', 'ip', 'content', 'create_time')

    list_filter = ('ip', 'group', 'create_time')

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(group=self.model._meta.app_label)


class TaskClientAdmin(admin.ModelAdmin):
    list_display = ('client_id', 'container_id', 'container_name',
                    'admin_subscription_url',
                    'startup_status', 'container_status',
                    'stop_client', 'show_log', 'create_time')
    form = forms.TaskClientForm
    fields = (
        'run_in_container',
        'container_image',
        'container_name',
        'system_subscription_url',
        ('system_subscription_scheme', 'system_subscription_host', 'system_subscription_port'),
        'custom_subscription_url',
        'subscription_kwargs',
        'settings',
        'env',
        'process_id',
        'container_id',
        'create_time',
    )

    list_filter = ('container_status',)
    readonly_fields = ('create_time', )

    def admin_subscription_url(self, obj):
        url = urlparse(obj.subscription_url)
        return format_html(
            '<a href="%s" target="_blank">%s</a>' % (
                obj.subscription_url, url.path
            )
        )
    admin_subscription_url.short_description = '订阅地址'

    def stop_client(self, obj):
        url = reverse('system-client-stop', args=(obj.pk,))
        return format_html(
            '<a href="%s" target="_blank">停止</a>' % url
        )
    stop_client.short_description = '停止运行'

    def show_log(self, obj):
        url = reverse('system-client-log', args=(obj.pk,))
        return format_html(
            '<a href="%s" target="_blank">查看日志</a>' % url
        )
    show_log.short_description = '日志'

    containers_loaded = False

    def load_local_containers(self, request):
        if not self.containers_loaded:
            TaskClientAdmin.containers_loaded = True
            try:
                client = docker.from_env()
                containers = client.containers.list(all=True, filters={
                    "name": "common-task-system-client",
                    "ancestor": "common-task-system-client"
                })
            except APIError as e:
                self.message_user(request, '获取客户端异常: %s' % e, level=messages.ERROR)
            else:
                for container in containers:
                    kwargs = {x.split('=')[0].strip('-'): x.split('=')[1] for x in container.attrs['Args']}
                    subscription_url = kwargs.pop('subscription-url', None)
                    try:
                        match = resolve(urlparse(subscription_url).path)
                    except Resolver404:
                        group = 'remote'
                    else:
                        if match.url_name == 'system-schedule-get':
                            group = 'SystemTaskClient'
                        else:
                            group = 'UserTaskClient'
                    client = self.model(
                        group=group,
                        container_id=container.short_id,
                        container_name=container.name,
                        container_image=';'.join(container.image.tags[:1]),
                        container_status=container.status.capitalize(),
                        subscription_url=subscription_url,
                        subscription_kwargs=kwargs,
                    )
                    client.container = container
                    client.save()

    def get_queryset(self, request):
        self.load_local_containers(request)
        return TaskClient.objects.filter(group=self.model.__name__)

    def has_change_permission(self, request, obj=None):
        return False
