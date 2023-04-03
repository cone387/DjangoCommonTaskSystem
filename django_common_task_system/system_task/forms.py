from . import models
from .choices import SystemTaskType
from django import forms


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
        if cleaned_data.get('task_type') == SystemTaskType.SQL_TASK_PRODUCE:
            queue = cleaned_data.pop('queue')
            if not queue:
                self.add_error('queue', '队列不能为空')
            else:
                cleaned_data['config']['queue'] = queue.code
        return cleaned_data

    class Meta:
        model = models.SystemTask
        fields = '__all__'
