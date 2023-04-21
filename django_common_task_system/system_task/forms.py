from . import models
from django import forms
import os
import time
from .process import ProcessManager
from ..system_task_execution.main import start_system_client
from django_common_task_system.forms import TaskScheduleProducerForm, TaskScheduleQueueForm


class SystemTaskForm(forms.ModelForm):
    queue = forms.ModelChoiceField(
        queryset=models.SystemScheduleQueue.objects.all(),
        required=False,
        label='队列',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        super(SystemTaskForm, self).__init__(*args, **kwargs)
        if self.instance.id:
            if self.instance.parent is not None and \
                    self.instance.parent == models.builtins.tasks.sql_produce_parent_task:
                self.fields['queue'].initial = models.SystemScheduleQueue.objects.get(
                    code=self.instance.config.get('queue')
                )

    def clean(self):
        cleaned_data = super(SystemTaskForm, self).clean()
        parent = cleaned_data.get('parent')
        required_fields = parent.config.get('required_fields', []) if parent else []
        config = cleaned_data.get('config', {})
        queue = cleaned_data.pop('queue')
        if queue:
            config['queue'] = queue.code
        for field in required_fields:
            if not config.get(field):
                self.add_error('config', '%s不能为空' % field)
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
            self.initial['log_file'] = os.path.join(logs_path,
                                                    'system-process-%s.log' % time.strftime('%Y%m%d%H%M%S'))

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
