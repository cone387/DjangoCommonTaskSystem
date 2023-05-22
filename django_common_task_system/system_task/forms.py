from . import models
from django import forms
import os
import time
import hashlib
from .process import ProcessManager
from ..system_task_execution.main import start_system_client
from django_common_objects.widgets import JSONWidget
from django.conf import settings
from django_common_task_system.forms import (
    TaskScheduleProducerForm, TaskScheduleQueueForm, CustomProgramField
)


class InitialFileStr(str):

    @property
    def url(self):
        return self


def get_md5(text):
    md5 = hashlib.md5()
    md5.update(text.encode('utf-8'))
    return md5.hexdigest()


class SystemTaskForm(forms.ModelForm):
    config = forms.JSONField(
        label='配置',
        widget=JSONWidget(attrs={'style': 'width: 70%;'}),
        initial={},
        required=False,
    )
    queue = forms.ModelChoiceField(
        queryset=models.SystemScheduleQueue.objects.all(),
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
    # 不知道为什么这里使用validators时，在admin新增任务时如果validator没通过，第一次会报错，第二次就不会报错了
    custom_program = CustomProgramField(required=False, help_text='仅支持zip、python、shell格式')

    executable_path = os.path.join(settings.STATIC_ROOT or os.path.join(os.getcwd(), 'static'), 'executable')

    def __init__(self, *args, **kwargs):
        super(SystemTaskForm, self).__init__(*args, **kwargs)
        if self.instance.id:
            queue = self.instance.config.get('queue')
            if queue:
                self.initial['queue'] = models.SystemScheduleQueue.objects.get(code=queue)
            self.initial['script'] = self.instance.config.get('script')
            self.initial['include_meta'] = self.instance.config.get('include_meta')
            program = self.instance.config.get('program')
            if program:
                executable = InitialFileStr(program.get('executable', '').replace(self.executable_path, ''))
                self.initial['custom_program'] = [
                    executable,
                    program.get('args'),
                    program.get('docker_image'),
                    program.get('run_in_docker', False),
                ]

    def clean(self):
        cleaned_data = super(SystemTaskForm, self).clean()
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
            elif field == 'custom_program':
                if isinstance(value, str):
                    config[field] = value
                    continue
                max_size = parent.config.get('max_size', 5 * 1024 * 1024)
                bytesio, args, docker_image, run_in_docker = value
                if bytesio.size > max_size:
                    self.add_error('name', '文件大小不能超过%sM' % round(max_size / 1024 / 1024))
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
                config['executable'] = file
                config['args'] = args
                config['docker_image'] = docker_image
                config['run_in_docker'] = run_in_docker
            else:
                config[field] = value
        return cleaned_data

    class Meta:
        model = models.SystemTask
        fields = '__all__'


class ReadOnlyWidget(forms.TextInput):

    def __init__(self, attrs=None):
        attrs = attrs or {
            'readonly': 'readonly',
            'style': 'border:none; width: 60%;'
        }
        super(ReadOnlyWidget, self).__init__(attrs=attrs)


class SystemProcessForm(forms.ModelForm):
    process_id = forms.IntegerField(initial=0, widget=ReadOnlyWidget())
    system_path = forms.CharField(max_length=100, label='系统路径',
                                  initial=os.getcwd(),
                                  widget=ReadOnlyWidget())
    process_name = forms.CharField(max_length=100, label='进程名称',
                                   initial='common-task-system-process',
                                   widget=forms.TextInput(attrs={'style': 'width: 60%;'}))
    env = forms.CharField(
        max_length=500,
        initial='DJANGO_SETTINGS_MODULE=%s' % os.environ.get('DJANGO_SETTINGS_MODULE'),
        widget=forms.Textarea(attrs={'style': 'width: 60%;', "cols": "40", "rows": "5"}),
    )
    log_file = forms.CharField(max_length=200, label='日志文件', initial='system_process.log',
                               widget=forms.TextInput(attrs={'style': 'width: 60%;'}))

    def __init__(self, *args, **kwargs):
        super(SystemProcessForm, self).__init__(*args, **kwargs)
        if not self.instance.id:
            logs_path = os.path.join(os.getcwd(), 'logs')
            self.initial['log_file'] = os.path.join(logs_path, 'system-process-%s.log' % time.strftime('%Y%m%d%H%M%S'))

    def clean(self):
        cleaned_data = super(SystemProcessForm, self).clean()
        log_file = cleaned_data.get('log_file')
        try:
            p = ProcessManager.create(start_system_client, log_file=log_file)
        except Exception as e:
            self.add_error('endpoint', '启动失败: %s' % e)
            cleaned_data['status'] = False
        else:
            cleaned_data['process_id'] = p.pid
            cleaned_data['status'] = p.is_alive()
        return cleaned_data

    class Meta:
        model = models.SystemProcess
        fields = '__all__'


class SystemScheduleQueueForm(TaskScheduleQueueForm):

    class Meta(TaskScheduleQueueForm.Meta):
        model = models.SystemScheduleQueue


class SystemScheduleProducerForm(TaskScheduleProducerForm):

    class Meta(TaskScheduleProducerForm.Meta):
        model = models.SystemScheduleProducer
