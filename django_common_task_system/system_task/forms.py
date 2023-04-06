from . import models
from .choices import SystemTaskType
from django import forms
import os
import time


task_type_fields = {
    SystemTaskType.SQL_TASK_PRODUCE: (
        'queue',
        'sql',
    ),
    SystemTaskType.SQL_TASK_EXECUTION: (
        'sql',
    ),
    SystemTaskType.SHELL_EXECUTION: (
        'shell',
    )
}


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
            if self.instance.task_type == SystemTaskType.SQL_TASK_PRODUCE:
                self.fields['queue'].initial = models.SystemScheduleQueue.objects.get(
                    code=self.instance.config.get('queue')
                )

    def clean(self):
        cleaned_data = super(SystemTaskForm, self).clean()
        required_fields = task_type_fields[cleaned_data['task_type']]
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
    image = forms.CharField(max_length=100, label='镜像',
                            initial='common-task-system-process',
                            widget=ReadOnlyWidget())
    system_path = forms.CharField(max_length=100, label='系统路径',
                                  initial=os.getcwd(),
                                  widget=ReadOnlyWidget())
    system_setting = forms.CharField(max_length=100, label='系统设置',
                                     initial=os.environ.get('DJANGO_SETTINGS_MODULE'),
                                     widget=ReadOnlyWidget())
    container_name = forms.CharField(max_length=100, label='容器名称',
                                     initial='common-task-system-process',
                                     widget=forms.TextInput(attrs={'style': 'width: 60%;'}))

    def __init__(self, *args, **kwargs):
        super(SystemProcessForm, self).__init__(*args, **kwargs)
        if not self.instance.id:
            self.fields['container_name'].initial = 'common-task-system-process-%s' % time.strftime('%Y%m%d%H%M%S')

    class Meta:
        model = models.SystemProcess
        fields = '__all__'
