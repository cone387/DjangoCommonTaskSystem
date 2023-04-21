import inspect
from django import forms
from django.contrib.admin import widgets
from django.utils.module_loading import import_string
from .choices import TaskScheduleType, ScheduleTimingType, TaskScheduleStatus, TaskStatus
from django_common_objects.widgets import JSONWidget
from .utils import foreign_key
from datetime import datetime, time as datetime_time
from . import models


class TaskForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(TaskForm, self).__init__(*args, **kwargs)
        task: models.Task = self.instance
        if task.id:
            self.fields['parent'].queryset = models.Task.objects.filter(
                user=task.user
            ).exclude(id__in=foreign_key.get_related_object_ids(task))


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
        super().__init__(ws)

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


class TaskScheduleForm(forms.ModelForm):
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
        super(TaskScheduleForm, self).__init__(*args, **kwargs)
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
        cleaned_data = super(TaskScheduleForm, self).clean()
        cleaned_data.pop("config", None)
        schedule = models.ScheduleConfig(**cleaned_data)
        cleaned_data['config'] = schedule.config
        cleaned_data['next_schedule_time'] = schedule.get_current_time(
            start_time=cleaned_data.get('schedule_start_time', None)
        )
        return cleaned_data

    class Meta:
        model = models.TaskSchedule
        fields = "__all__"


class TaskScheduleQueueForm(forms.ModelForm):

    def clean(self):
        cleaned_data = super(TaskScheduleQueueForm, self).clean()
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
        model = models.TaskScheduleQueue
        fields = '__all__'


class TaskScheduleProducerForm(forms.ModelForm):
    name = forms.CharField(max_length=100, label='名称', required=False)

    def __init__(self, *args, **kwargs):
        super(TaskScheduleProducerForm, self).__init__(*args, **kwargs)
        if not self.instance.id:
            self. initial['filters'] = {
                'status': TaskScheduleStatus.OPENING.value,
                'task__status': TaskStatus.ENABLE.value,
            }

    def clean(self):
        cleaned_data = super(TaskScheduleProducerForm, self).clean()
        if not self.errors:
            filters = cleaned_data.get('filters')
            if not filters:
                self.add_error('filters', 'filters不能为空')
            else:
                try:
                    models.TaskSchedule.objects.filter(**filters).first()
                except Exception as e:
                    self.add_error('filters', 'filters参数错误: %s' % e)
                else:
                    name = cleaned_data.get('name')
                    if not name:
                        cleaned_data['name'] = "队列(%s)生产者" % cleaned_data.get('queue').name
        return cleaned_data

    class Meta:
        model = models.TaskScheduleProducer
        fields = '__all__'


class ConsumerPermissionForm(forms.ModelForm):
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

