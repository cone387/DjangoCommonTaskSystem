from django import forms
from django.contrib.admin import widgets
from datetime import datetime
from django_common_task_system.choices import ScheduleTimingType


class CustomProgramWidget(forms.MultiWidget):
    template_name = 'schedule/custom_program.html'

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
    template_name = 'schedule/sql_config.html'

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



class DateTimeRangeWidget(forms.widgets.MultiWidget):
    template_name = 'schedule/datetime_range.html'

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
    template_name = 'schedule/period.html'

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
    template_name = 'schedule/period_schedule.html'

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
    template_name = 'schedule/multi_day_select.html'

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

    template_name = 'schedule/multi_monthday_select.html'

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
    template_name = 'schedule/multi_month_day_select.html'

    class Media:
        css = {
            'all': ('common_task_system/css/calendar.css',)
        }
        js = ('common_task_system/js/calendar.js',)


class NLPSentenceWidget(forms.TextInput):
    template_name = 'schedule/nlp_input.html'

