from . import models
from .choices import SystemTaskType
from django import forms


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
