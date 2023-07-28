
import inspect
import os
import time
from django import forms
from django.conf import settings
from django.contrib.admin import widgets
from django.utils.module_loading import import_string
from django_common_task_system.choices import (
    ScheduleType, ScheduleTimingType, ScheduleStatus, TaskStatus)
from django_common_objects.widgets import JSONWidget
from django_common_task_system.utils import foreign_key
from datetime import datetime, time as datetime_time
from .schedule.config import ScheduleConfig
from django.urls import reverse
from django_common_task_system.utils import ip as ip_utils
from urllib.parse import urljoin
from django_common_task_system.utils.cache import ttl_cache
from . import models
from .builtins import builtins
from . import get_schedule_model, get_task_model
from .fields import (NLPSentenceWidget, PeriodScheduleFiled, OnceScheduleField, MultiWeekdaySelectFiled,
                     MultiMonthdaySelectFiled, MultiYearDaySelectWidget, MultiDaySelectField, PeriodWidget,
                     SqlConfigField, CustomProgramField)
from .utils.algorithm import get_md5

TaskModel = get_task_model()
ScheduleModel = get_schedule_model()


class InitialFileStr(str):

    @property
    def url(self):
        return self


class TaskForm(forms.ModelForm):

    config = forms.JSONField(
        label='配置',
        widget=JSONWidget(attrs={'style': 'width: 70%;'}),
        initial={},
        required=False,
    )
    queue = forms.ModelChoiceField(
        queryset=models.ScheduleQueue.objects.all(),
        required=False,
        label='任务队列',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    include_meta = forms.BooleanField(
        label='包含元数据',
        required=False,
        initial=True
    )

    script = forms.CharField(
        label='脚本',
        widget=forms.Textarea(attrs={'style': 'width: 70%;'}),
        required=False
    )
    sql_config = SqlConfigField(required=False, label="SQL源", help_text="仅支持MySQL, 默认当前数据库")
    # 不知道为什么这里使用validators时，在admin新增任务时如果validator没通过，第一次会报错，第二次就不会报错了
    custom_program = CustomProgramField(required=False, help_text='仅支持zip、python、shell格式')

    executable_path = os.path.join(settings.STATIC_ROOT or os.path.join(os.getcwd(), 'static'), 'executable')

    def __init__(self, *args, **kwargs):
        super(TaskForm, self).__init__(*args, **kwargs)
        task = self.instance
        if task.id:
            self.fields['parent'].queryset = self._meta.model.objects.filter(
                user=task.user
            ).exclude(id__in=foreign_key.get_related_object_ids(task))

            config = self.instance.config
            queue = config.get('queue')
            if queue:
                self.initial['queue'] = models.ScheduleQueue.objects.get(code=queue)
            self.initial['script'] = config.get('script')
            self.initial['include_meta'] = config.get('include_meta')
            custom_program = config.get('custom_program')
            if custom_program:
                self.initial['custom_program'] = [
                    InitialFileStr(custom_program.get('executable', '').replace(self.executable_path, '')),
                    custom_program.get('args'),
                    custom_program.get('docker_image'),
                    custom_program.get('run_in_docker', False),
                ]
            sql_config = config.get('sql_config')
            if sql_config:
                self.initial['sql_config'] = [
                    sql_config.get('host'),
                    sql_config.get('port'),
                    sql_config.get('database'),
                    sql_config.get('user'),
                    sql_config.get('password'),
                ]

    def clean(self):
        cleaned_data = super(TaskForm, self).clean()
        if self.errors:
            return None
        parent = cleaned_data.get('parent')
        required_fields = parent.config.get('required_fields', []) if parent else []
        config = cleaned_data.setdefault('config', {})
        if not config:
            config = cleaned_data['config'] = {}
        for field in required_fields:
            value = cleaned_data.pop(field, None) or config.pop(field, None)
            if not value:
                self.add_error('name', '%s不能为空' % field)
                break
            if field == 'queue':
                config[field] = value.code
            elif field == 'sql_config':
                host, port, database, user, password = value
                if host:
                    config[field] = {
                        'host': host,
                        'port': port,
                        'database': database,
                        'user': user,
                        'password': password,
                    }
            elif field == 'custom_program':
                bytesio, args, docker_image, run_in_docker = value
                if not bytesio:
                    custom_program = config.pop(field, None)
                    if not custom_program or not custom_program.get('executable'):
                        self.add_error('custom_program', '自定义程序不能为空')
                    else:
                        config[field] = {
                            'executable': custom_program.get('executable'),
                            'args': args,
                            'docker_image': docker_image,
                            'run_in_docker': run_in_docker,
                        }
                    break
                max_size = parent.config.get('max_size', 5 * 1024 * 1024)
                bytesio, args, docker_image, run_in_docker = value
                if bytesio.size > max_size:
                    self.add_error('custom_program', '文件大小不能超过%sM' % round(max_size / 1024 / 1024))
                    break
                path = os.path.join(self.executable_path, get_md5(cleaned_data['name']))
                if not os.path.exists(path):
                    os.makedirs(path)
                file = os.path.join(path, 'main%s' % os.path.splitext(bytesio.name)[-1])
                with open(file, 'wb') as f:
                    trunk = bytesio.read(bytesio.DEFAULT_CHUNK_SIZE)
                    while trunk:
                        f.write(trunk)
                        trunk = bytesio.read(bytesio.DEFAULT_CHUNK_SIZE)
                config[field] = {
                    'executable': file,
                    'args': args,
                    'docker_image': docker_image,
                    'run_in_docker': run_in_docker,
                }
            else:
                config[field] = value
        return cleaned_data

    class Meta:
        fields = '__all__'
        model = TaskModel


class ScheduleForm(forms.ModelForm):
    schedule_type = forms.ChoiceField(required=True, label="计划类型", choices=ScheduleType.choices)
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
            if schedule_type == ScheduleType.CONTINUOUS:
                t = datetime.strptime(type_config['schedule_start_time'], '%Y-%m-%d %H:%M:%S')
                self.initial['period_schedule'] = [t, type_config['period']]
            elif schedule_type == ScheduleType.ONCE:
                self.initial['once_schedule'] = datetime.strptime(type_config['schedule_start_time'],
                                                                  '%Y-%m-%d %H:%M:%S')
            elif schedule_type == ScheduleType.CRONTAB:
                self.initial['crontab'] = type_config['crontab']
            elif schedule_type == ScheduleType.TIMINGS:
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
        else:
            self.initial['callback'] = builtins.schedule_callbacks.log_upload

    def clean(self):
        cleaned_data = super(ScheduleForm, self).clean()
        cleaned_data.pop("config", None)
        schedule = ScheduleConfig(**cleaned_data)
        cleaned_data['config'] = schedule.config
        cleaned_data['next_schedule_time'] = schedule.get_current_time(
            start_time=cleaned_data.get('schedule_start_time', None)
        )
        base_on_now = cleaned_data.get('base_on_now', False)
        is_strict = cleaned_data.get('is_strict', False)
        if is_strict and base_on_now:
            raise forms.ValidationError("严格模式下不允许基于当前时间")
        self.instance.update_time = datetime.now()
        return cleaned_data

    class Meta:
        fields = "__all__"


class ScheduleQueueForm(forms.ModelForm):

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
    name = forms.CharField(max_length=100, label='名称', required=False)

    def __init__(self, *args, **kwargs):
        super(ScheduleProducerForm, self).__init__(*args, **kwargs)
        if not self.instance.id:
            self. initial['filters'] = {
                'status': ScheduleStatus.OPENING.value,
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
                    ScheduleModel.objects.filter(**filters).first()
                except Exception as e:
                    self.add_error('filters', 'filters参数错误: %s' % e)
                else:
                    name = cleaned_data.get('name')
                    if not name:
                        cleaned_data['name'] = "队列(%s)生产者" % cleaned_data.get('queue').name
        return cleaned_data

    class Meta:
        fields = '__all__'
        model = ScheduleModel


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

    class Meta:
        fields = '__all__'
        model = models.ScheduleQueuePermission


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
        queryset = models.ScheduleQueue.objects.filter(status=True)
        for obj in queryset:
            path = reverse('schedule-get', kwargs={'code': obj.code})
            subscription_url_choices.append((path, obj.name))
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
        client: models.TaskClient = self.instance
        for f in models.TaskClient._meta.fields:
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
        model = models.TaskClient
        fields = '__all__'

