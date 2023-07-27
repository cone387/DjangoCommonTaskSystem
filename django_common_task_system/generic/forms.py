import inspect
import os
import time
from django import forms
from django.contrib.admin import widgets
from django.utils.module_loading import import_string
from django_common_task_system.generic.choices import (
    TaskScheduleType, ScheduleTimingType, TaskScheduleStatus, TaskStatus)
from django_common_task_system.generic.models import TaskClient, AbstractTaskSchedule, AbstractTaskScheduleQueue
from django_common_objects.widgets import JSONWidget
from django_common_task_system.utils import foreign_key
from datetime import datetime, time as datetime_time
from .schedule_config import ScheduleConfig
from django.forms.renderers import DjangoTemplates
from pathlib import Path
from django.conf import settings as django_settings
from django.urls import reverse
from django_common_task_system.utils import ip as ip_utils
from urllib.parse import urljoin
from django_common_task_system.utils.cache import ttl_cache

template_path = Path(__file__).parent.parent / 'templates'
common_task_system_renderer = DjangoTemplates()
common_task_system_renderer.engine.engine.dirs.append(template_path)
django_settings.TEMPLATES[0]['DIRS'].append(str(template_path))


class CustomProgramWidget(forms.MultiWidget):
    template_name = 'task_schedule/custom_program.html'

    def __init__(self, attrs=None):
        file = widgets.AdminFileWidget()
        args = widgets.AdminTextInputWidget(attrs={'style': 'width: 60%; margin-top: 1px; ',
                                                   'placeholder': '例如: -a 1 -b 2'})
        container_image = widgets.AdminTextInputWidget(
            attrs={'style': 'margin-top: 1px; ', 'placeholder': 'common-task-system-client:latest'})
        run_in_container = forms.CheckboxInput()
        super().__init__([file, args, container_image, run_in_container], attrs=attrs)

    def decompress(self, value):
        if value:
            return value
        return [None, None, None, False]


class CustomProgramField(forms.MultiValueField):
    widget = CustomProgramWidget

    def __init__(self, required=False, label="可执行文件", initial=None, **kwargs):
        if initial is None:
            initial = [None, None, None, False]
        a, b, c, d = initial
        fs = (
            forms.FileField(help_text='仅支持zip、python、shell格式', required=False, initial=a),
            forms.CharField(help_text='例如: -a 1 -b 2', required=False, initial=b),
            forms.CharField(help_text='Docker镜像', required=False, initial=c),
            forms.BooleanField(label="在Docker中运行", help_text='在Docker中运行', initial=d),
        )
        super(CustomProgramField, self).__init__(fs, required=required, label=label, **kwargs)

    def compress(self, data_list):
        return data_list

    def validate(self, value):
        super(CustomProgramField, self).validate(value)
        file, args, *_ = value
        if file:
            ext = file.name.split('.')[-1]
            if ext not in ['zip', 'py', 'sh']:
                raise forms.ValidationError('仅支持zip、python、shell格式')


class SqlConfigWidget(forms.MultiWidget):
    template_name = 'task_schedule/sql_config.html'

    def __init__(self, attrs=None):
        host = widgets.AdminTextInputWidget()
        port = widgets.AdminIntegerFieldWidget()
        db = widgets.AdminTextInputWidget(attrs={'style': 'width: 120px'})
        user = widgets.AdminTextInputWidget()
        pwd = widgets.AdminTextInputWidget(attrs={'type': 'password'})
        super().__init__([host, port, db, user, pwd], attrs=attrs)

    def decompress(self, value):
        if value:
            return value
        return [None, 3306, None, 'root', None]


class SqlConfigField(forms.MultiValueField):
    widget = SqlConfigWidget

    def __init__(self, required=False, label="SQL配置", initial=None, **kwargs):
        if initial is None:
            initial = [None, 3306, None, 'root', None]
        a, b, c, d, e = initial
        fs = (
            forms.CharField(help_text='仅支持zip、python、shell格式', required=False, initial=a),
            forms.IntegerField(help_text='端口', required=False, initial=b),
            forms.CharField(help_text='DB', required=False, initial=c),
            forms.CharField(help_text='用户名', required=False, initial=d),
            forms.CharField(help_text='在Docker中运行', initial=e),
        )
        super(SqlConfigField, self).__init__(fs, required=required, label=label, **kwargs)

    def compress(self, data_list):
        return data_list

    def validate(self, value):
        super(SqlConfigField, self).validate(value)
        host, port, db, user, pwd = value
        if host:
            import pymysql
            try:
                pymysql.connect(host=host, port=port, db=db, user=user, password=pwd)
            except Exception as e:
                raise forms.ValidationError('连接失败: {}'.format(e))


class TaskForm(forms.ModelForm):
    default_renderer = common_task_system_renderer

    def __init__(self, *args, **kwargs):
        super(TaskForm, self).__init__(*args, **kwargs)
        task = self.instance
        if task.id:
            self.fields['parent'].queryset = self._meta.model.objects.filter(
                user=task.user
            ).exclude(id__in=foreign_key.get_related_object_ids(task))

    class Meta:
        fields = '__all__'


class DateTimeRangeWidget(forms.widgets.MultiWidget):
    template_name = 'task_schedule/datetime_range.html'

    def __init__(self, attrs=None):
        st = widgets.AdminSplitDateTime()
        et = widgets.AdminSplitDateTime()
        super().__init__([st, et], attrs=attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["start_datetime"] = "开始时间:"
        context["end_datetime"] = "结束时间:"
        return context

    def decompress(self, value):
        if value:
            return value
        return [None, None]


class PeriodWidget(widgets.AdminIntegerFieldWidget):
    template_name = 'task_schedule/period.html'

    def __init__(self, unit=ScheduleTimingType.DAY.value, attrs=None):
        self.unit = unit
        super().__init__(attrs=attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["unit"] = self.unit
        return context


class NullableSplitDateTimeField(forms.SplitDateTimeField):

    def clean(self, value):
        if value[0] and not value[1]:
            value[1] = '00:00:00'
        elif not value[0] and value[1]:
            value[0] = datetime.now().strftime('%Y-%m-%d')
        return super(NullableSplitDateTimeField, self).clean(value)


class MultiWeekdaySelectFiled(forms.MultipleChoiceField):
    _choices = [
        (1, "星期一"),
        (2, "星期二"),
        (3, "星期三"),
        (4, "星期四"),
        (5, "星期五"),
        (6, "星期六"),
        (7, "星期日"),
    ]
    widget = forms.CheckboxSelectMultiple

    def __init__(self, *, choices=(), label="星期", widget=None, **kwargs):
        super(MultiWeekdaySelectFiled, self).__init__(
            choices=choices or self._choices,
            label=label,
            widget=widget or self.widget,
            **kwargs)

    def to_python(self, value):
        if not value:
            return value
        elif not isinstance(value, (list, tuple)):
            raise forms.ValidationError(
                self.error_messages["invalid_list"], code="invalid_list"
            )
        return [int(val) for val in value]


class PeriodScheduleWidget(forms.MultiWidget):
    template_name = 'task_schedule/period_schedule.html'

    def __init__(self, default_time=datetime.now, default_period=60, attrs=None):
        ws = (
            widgets.AdminSplitDateTime(),
            widgets.AdminIntegerFieldWidget()
        )
        self.default_time = default_time() if callable(default_time) else default_time
        self.default_period = default_period
        super().__init__(ws, attrs=attrs)

    def decompress(self, value):
        if value:
            return value
        return [self.default_time, self.default_period]


class PeriodScheduleFiled(forms.MultiValueField):
    widget = PeriodScheduleWidget

    def __init__(self, label="持续计划", **kwargs):
        fs = (
            forms.SplitDateTimeField(help_text="下次开始时间"),
            forms.IntegerField(help_text="周期/每(秒)")
        )
        super(PeriodScheduleFiled, self).__init__(fs, label=label, **kwargs)

    def to_python(self, value):
        if not value:
            return []
        elif not isinstance(value, (list, tuple)):
            raise forms.ValidationError(
                self.error_messages["invalid_list"], code="invalid_list"
            )
        return [int(val) for val in value]

    def compress(self, data_list):
        return data_list


class OnceScheduleField(forms.SplitDateTimeField):
    widget = widgets.AdminSplitDateTime

    def __init__(self, required=False, label="计划时间", **kwargs):
        super(OnceScheduleField, self).__init__(
            required=required,
            label=label,
            initial=datetime.now(), **kwargs)


class MultiDaySelectWidget(forms.MultiWidget):
    template_name = 'task_schedule/multi_day_select.html'

    def __init__(self, attrs=None):
        ws = (
            forms.TextInput(attrs={'style': "width: 80%;"}),
            widgets.AdminTimeWidget(attrs={'style': "margin-top: 5px;"})
        )
        super(MultiDaySelectWidget, self).__init__(ws, attrs=attrs)

    def decompress(self, value):
        if value:
            return value
        return [None, None]

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['date_label'] = "日期："
        context['time_label'] = "时间："
        return context

    class Media:
        css = {
            'all': ('common_task_system/css/calendar.css',)
        }
        js = ('common_task_system/js/calendar.js',)


class MultiDaySelectField(forms.MultiValueField):
    widget = MultiDaySelectWidget

    def __init__(self, required=False, label="自选日期", **kwargs):
        fs = (
            forms.CharField(),
            forms.TimeField()
        )
        super(MultiDaySelectField, self).__init__(fs, required=required, label=label, **kwargs)

    def compress(self, data_list):
        return data_list

    def decompress(self, value):
        if value:
            return value
        return [None, None]


class MultiMonthdaySelectFiled(forms.MultipleChoiceField):
    _choices = [
        (0, "每月第一天"),
        (32, "每月最后一天"),
        (1, "1号"),
        (2, "2号"),
        (3, "3号"),
        (4, "4号"),
        (5, "5号"),
        (6, "6号"),
        (7, "7号"),
        (8, "8号"),
        (9, "9号"),
        (10, "10号"),
        (11, "11号"),
        (12, "12号"),
        (13, "13号"),
        (14, "14号"),
        (15, "15号"),
        (16, "16号"),
        (17, "17号"),
        (18, "18号"),
        (19, "19号"),
        (20, "20号"),
        (21, "21号"),
        (22, "22号"),
        (23, "23号"),
        (24, "24号"),
        (25, "25号"),
        (26, "26号"),
        (27, "27号"),
        (28, "28号"),
        (29, "29号"),
        (30, "30号"),
        (31, "31号"),
    ]
    widget = forms.CheckboxSelectMultiple()

    template_name = 'task_schedule/multi_monthday_select.html'

    def __init__(self, *, choices=(), label="日期", widget=None, **kwargs):
        super(MultiMonthdaySelectFiled, self).__init__(
            choices=choices or self._choices,
            label=label,
            widget=widget or self.widget,
            **kwargs)

    def to_python(self, value):
        if not value:
            return []
        elif not isinstance(value, (list, tuple)):
            raise forms.ValidationError(
                self.error_messages["invalid_list"], code="invalid_list"
            )
        return [int(val) for val in value]


class MultiYearDaySelectWidget(forms.TextInput):
    template_name = 'task_schedule/multi_month_day_select.html'

    class Media:
        css = {
            'all': ('common_task_system/css/calendar.css',)
        }
        js = ('common_task_system/js/calendar.js',)


class NLPSentenceWidget(forms.TextInput):
    template_name = 'task_schedule/nlp_input.html'


class ScheduleForm(forms.ModelForm):
    default_renderer = common_task_system_renderer

    schedule_type = forms.ChoiceField(required=True, label="计划类型", choices=TaskScheduleType.choices)
    base_on_now = forms.BooleanField(required=False, label="基于当前时间", initial=False)
    next_schedule_time = forms.DateTimeField(required=False, label='下次计划时间',
                                             widget=forms.TextInput(attrs={'readonly': 'readonly'}))
    nlp_sentence = forms.CharField(required=False, label="NLP", help_text="自然语言，如：每天早上8点",
                                   widget=NLPSentenceWidget(attrs={'style': "width: 60%;"}))
    crontab = forms.CharField(required=False, label="Crontab表达式", help_text="crontab表达式，如：* * * * *")
    period_schedule = PeriodScheduleFiled()
    once_schedule = OnceScheduleField()
    timing_type = forms.ChoiceField(required=False, label="指定时间", choices=ScheduleTimingType.choices)
    timing_weekday = MultiWeekdaySelectFiled(required=False)
    timing_monthday = MultiMonthdaySelectFiled(required=False)
    timing_year = forms.CharField(required=False, label="选择日期",
                                  widget=MultiYearDaySelectWidget(attrs={'style': "width: 60%;"}))
    timing_datetime = MultiDaySelectField()
    timing_period = forms.IntegerField(required=False, min_value=1, initial=1, label='频率', widget=PeriodWidget)
    timing_time = forms.TimeField(required=False, initial=datetime_time(),
                                  label="时间", widget=widgets.AdminTimeWidget)
    config = forms.JSONField(required=False, initial={}, label="配置",
                             widget=JSONWidget(attrs={'readonly': 'readonly'})
                             )

    def __init__(self, *args, **kwargs):
        super(ScheduleForm, self).__init__(*args, **kwargs)
        if self.instance.pk:
            config = self.instance.config
            schedule_type = config.get('schedule_type')
            self.initial['schedule_type'] = schedule_type
            type_config = config[schedule_type]
            self.initial['nlp_sentence'] = config.get('nlp-sentence')
            self.initial['base_on_now'] = config.get('base_on_now', False)
            if schedule_type == TaskScheduleType.CONTINUOUS:
                t = datetime.strptime(type_config['schedule_start_time'], '%Y-%m-%d %H:%M:%S')
                self.initial['period_schedule'] = [t, type_config['period']]
            elif schedule_type == TaskScheduleType.ONCE:
                self.initial['once_schedule'] = datetime.strptime(type_config['schedule_start_time'],
                                                                  '%Y-%m-%d %H:%M:%S')
            elif schedule_type == TaskScheduleType.CRONTAB:
                self.initial['crontab'] = type_config['crontab']
            elif schedule_type == TaskScheduleType.TIMINGS:
                timing_type = type_config.get('type')
                timing_config = type_config.get(timing_type, {})
                self.initial['timing_type'] = timing_type
                self.initial['timing_time'] = type_config['time']
                self.initial['timing_period'] = timing_config.get('period', 1)
                if timing_type == ScheduleTimingType.WEEKDAY:
                    self.initial['timing_weekday'] = timing_config.get('weekday')
                elif timing_type == ScheduleTimingType.MONTHDAY:
                    self.initial['timing_monthday'] = timing_config.get('monthday')
                elif timing_type == ScheduleTimingType.YEAR:
                    self.initial['timing_year'] = timing_config.get('year')
                elif timing_type == ScheduleTimingType.DATETIME:
                    self.initial['timing_datetime'] = timing_config.get('datetime')

    def clean(self):
        cleaned_data = super(ScheduleForm, self).clean()
        cleaned_data.pop("config", None)
        schedule = ScheduleConfig(**cleaned_data)
        cleaned_data['config'] = schedule.config
        cleaned_data['next_schedule_time'] = schedule.get_current_time(
            start_time=cleaned_data.get('schedule_start_time', None)
        )
        base_on_now = cleaned_data.get('base_on_now', False)
        strict_mode = cleaned_data.get('strict_mode', False)
        if strict_mode and base_on_now:
            raise forms.ValidationError("严格模式下不允许基于当前时间")
        if self.instance.id:
            if self.instance.config != schedule.config:
                schedule.config['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        else:
            schedule.config['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return cleaned_data

    class Meta:
        fields = "__all__"


class ScheduleQueueForm(forms.ModelForm):

    default_renderer = common_task_system_renderer

    def clean(self):
        cleaned_data = super(ScheduleQueueForm, self).clean()
        if not self.errors:
            module = cleaned_data.get('module')
            config = cleaned_data.get('config')
            config.setdefault('name', 'SYSTEM_TASK_QUEUE:%s' % cleaned_data['code'])
            queueCls = import_string(module)
            validate_config = getattr(queueCls, 'validate_config', None)
            if validate_config:
                error = validate_config(config)
                if error:
                    self.add_error('config', error)
            if not self.errors:
                args = inspect.getfullargspec(getattr(queueCls, '__init__'))
                kwargs = {k: v for k, v in config.items() if k in args.args}
                if 'name' not in kwargs:
                    config.pop('name')
                queue = queueCls(**kwargs)
                validate = getattr(queue, 'validate', None)
                if validate:
                    error = validate()
                    if error:
                        self.add_error('config', error)
        return cleaned_data

    class Meta:
        fields = '__all__'


class ScheduleProducerForm(forms.ModelForm):
    default_renderer = common_task_system_renderer
    schedule_model: AbstractTaskSchedule = None
    name = forms.CharField(max_length=100, label='名称', required=False)

    def __init__(self, *args, **kwargs):
        super(ScheduleProducerForm, self).__init__(*args, **kwargs)
        if not self.instance.id:
            self. initial['filters'] = {
                'status': TaskScheduleStatus.OPENING.value,
                'task__status': TaskStatus.ENABLE.value,
            }

    def clean(self):
        cleaned_data = super(ScheduleProducerForm, self).clean()
        if not self.errors:
            filters = cleaned_data.get('filters')
            if not filters:
                self.add_error('filters', 'filters不能为空')
            else:
                try:
                    self.schedule_model.objects.filter(**filters).first()
                except Exception as e:
                    self.add_error('filters', 'filters参数错误: %s' % e)
                else:
                    name = cleaned_data.get('name')
                    if not name:
                        cleaned_data['name'] = "队列(%s)生产者" % cleaned_data.get('queue').name
        return cleaned_data

    class Meta:
        fields = '__all__'


class ConsumerPermissionForm(forms.ModelForm):
    default_renderer = common_task_system_renderer
    config = forms.JSONField(required=False, initial={}, label="配置",
                             widget=forms.HiddenInput())
    ip_whitelist = forms.CharField(required=False, label="IP白名单", widget=forms.Textarea(
        attrs={'rows': 10, 'style': 'width: 60%'}))

    def __init__(self, *args, **kwargs):
        super(ConsumerPermissionForm, self).__init__(*args, **kwargs)
        if self.instance.id:
            self.initial['ip_whitelist'] = '\n'.join(self.instance.config.get('ip_whitelist', []) or [])

    def clean(self):
        cleaned_data = super(ConsumerPermissionForm, self).clean()
        if not self.errors:
            ip_whitelist = cleaned_data.pop('ip_whitelist', "")
            cleaned_data['config'] = {'ip_whitelist': [x.strip() for x in ip_whitelist.split('\n')]}
        return cleaned_data

    class Meta:
        fields = '__all__'


class ReadOnlyWidget(forms.TextInput):

    def __init__(self, attrs=None):
        attrs = attrs or {
            'readonly': 'readonly',
            'style': 'border:none; width: 60%;'
        }
        super(ReadOnlyWidget, self).__init__(attrs=attrs)


SETTINGS_TEMPLATE = """
# DISPATCHER = "task_system_client.task_center.dispatch.ParentAndOptionalNameDispatcher"
# SUBSCRIPTION = "task_system_client.task_center.subscription.HttpSubscription"
# EXECUTOR = "task_system_client.executor.base.ParentNameExecutor"
# SUBSCRIBER = "task_system_client.subscriber.BaseSubscriber"
# 异常处理
# EXCEPTION_HANDLER = "task_system_client.handler.exception.ExceptionHandler"
# EXCEPTION_REPORT_URL = None
# 并发控制， 为None则不限制
# SEMAPHORE = 10

"""


class TaskClientForm(forms.ModelForm):
    run_in_container = forms.BooleanField(label='在容器中运行', initial=True, required=False, widget=forms.HiddenInput())
    system_subscription_url = forms.ChoiceField(label='系统订阅地址', required=False)
    system_subscription_scheme = forms.ChoiceField(label='系统订阅Scheme',
                                                   choices={x: x for x in ['http', 'https']}.items())
    system_subscription_host = forms.ChoiceField(label='系统订阅Host')
    system_subscription_port = forms.IntegerField(label='系统订阅Port', initial=80, min_value=1, max_value=65535)
    custom_subscription_url = forms.CharField(
        max_length=300, label='自定义订阅地址', widget=forms.TextInput(
            attrs={'style': 'width: 60%;', 'placeholder': 'http://127.0.0.1:8000/task/subscription/'}),
        required=False, help_text="如果选择了此项，将使用此地址作为订阅地址，忽略选择的系统订阅地址"
    )
    subscription_kwargs = forms.CharField(max_length=500, label='订阅参数', widget=forms.Textarea(
        attrs={'rows': 1, 'style': 'width: 60%;',
               'placeholder': '{"queue": "test", "command": "select * from table limit 1"}'}
    ), required=False)
    process_id = forms.IntegerField(label="进程ID", widget=ReadOnlyWidget(), required=False)
    container_id = forms.CharField(max_length=100, label='容器ID', widget=ReadOnlyWidget(), required=False)
    container_image = forms.CharField(max_length=100, label='Docker镜像', widget=forms.TextInput(
        attrs={'style': 'width: 60%;', 'placeholder': 'cone387/common-task-system-client:latest'}
    ), required=False)
    container_name = forms.CharField(max_length=100, label='容器名', widget=forms.TextInput(
        attrs={'style': 'width: 60%;', 'placeholder': 'common-task-system-client'}
    ), required=False)
    settings = forms.CharField(
        label='配置',
        max_length=5000,
        initial=SETTINGS_TEMPLATE,
        widget=forms.Textarea(attrs={'style': 'width: 60%;', "cols": "40", "rows": len(SETTINGS_TEMPLATE.split('\n'))}),
    )
    env = forms.CharField(
        label='环境变量',
        max_length=500,
        initial='DJANGO_SETTINGS_MODULE=%s' % os.environ.get('DJANGO_SETTINGS_MODULE'),
        widget=forms.Textarea(attrs={'style': 'width: 60%;', "cols": "40", "rows": "5"}),
    )

    def __init__(self, *args, **kwargs):
        super(TaskClientForm, self).__init__(*args, **kwargs)
        subscription_url_choices = []
        for queue_model in AbstractTaskScheduleQueue.__subclasses__():
            app = queue_model._meta.app_label
            if app == 'django_common_task_system':
                reverse_name = 'user-schedule-get'
                name = '通用任务队列'
            elif app == 'system_task':
                reverse_name = 'system-schedule-get'
                name = '系统队列'
            else:
                continue
            queryset = queue_model.objects.filter(status=True)
            for obj in queryset:
                path = reverse(reverse_name, kwargs={'code': obj.code})
                subscription_url_choices.append((path, "%s-%s" % (name, obj.name)))
        self.fields['system_subscription_url'].choices = subscription_url_choices

        intranet_ip = ttl_cache()(ip_utils.get_intranet_ip)()
        internet_ip = self.get_internet_ip()
        ip_choices = (
            (intranet_ip, "%s(内网)" % intranet_ip),
            (internet_ip, "%s(外网)" % internet_ip),
            ('127.0.0.1', '127.0.0.1')
        )
        self.fields['system_subscription_host'].choices = ip_choices
        self.initial['system_subscription_port'] = os.environ['DJANGO_SERVER_ADDRESS'].split(':')[-1]

    def _post_clean(self):
        pass

    @staticmethod
    @ttl_cache()
    def get_internet_ip():
        try:
            return ip_utils.get_internet_ip()
        except Exception as e:
            return "获取失败: %s" % str(e)[:50]

    @staticmethod
    def validate_settings(client):
        try:
            exec(client.settings, None, client.settings_module)
        except Exception as e:
            raise forms.ValidationError('settings参数错误: %s' % e)

    def clean(self):
        cleaned_data = super(TaskClientForm, self).clean()
        if self.errors:
            return cleaned_data
        client: TaskClient = self.instance
        for f in TaskClient._meta.fields:
            setattr(client, f.name, cleaned_data.get(f.name))
        client.subscription_url = cleaned_data.get('custom_subscription_url') or urljoin(
            "%s://%s:%s" % (cleaned_data.get('system_subscription_scheme'),
                            cleaned_data.get('system_subscription_host'),
                            cleaned_data.get('system_subscription_port')),
            cleaned_data.get('system_subscription_url'))
        if client.subscription_url.startswith('redis'):
            if not client.subscription_kwargs.get('queue'):
                raise forms.ValidationError('queue is required for redis subscription')
        if client.subscription_url.startswith('mysql'):
            if not client.subscription_kwargs.get('command'):
                raise forms.ValidationError('command is required for mysql subscription')
        if not client.settings:
            self.add_error('settings', 'settings不能为空')
        self.validate_settings(client)
        if client.run_in_container:
            if not client.container_image:
                client.container_image = 'cone387/common-task-system-client:latest'
            if not client.container_name:
                client.container_name = 'common-task-system-client-%s' % time.strftime("%Y%m%d%H%M%S")
            # with open(client.settings_file, 'w', encoding='utf-8') as f:
            #     f.write(client.settings)
        return cleaned_data

    class Meta:
        model = TaskClient
        fields = '__all__'
