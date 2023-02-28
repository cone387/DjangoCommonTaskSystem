from .choices import TaskScheduleType
from .utils import cron_utils
from . import models
from django import forms
from django_common_objects.utils import foreign_key


class TaskForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(TaskForm, self).__init__(*args, **kwargs)
        task: models.Task = self.instance
        if task.id:
            self.fields['parent'].queryset = models.Task.objects.filter(
                user=task.user
            ).exclude(id__in=foreign_key.get_related_object_ids(task))


class TaskScheduleForm(forms.ModelForm):

    def clean(self):
        cleaned_data = super(TaskScheduleForm, self).clean()
        t = cleaned_data.get('type')
        if t == TaskScheduleType.CRONTAB:
            if not cleaned_data.get('crontab'):
                raise forms.ValidationError('crontab is required while type is crontab')
            cleaned_data['next_schedule_time'] = cron_utils.get_next_cron_time(cleaned_data['crontab'])
        elif t == TaskScheduleType.CONTINUOUS:
            if cleaned_data.get('period') == 0:
                raise forms.ValidationError("period can't be 0")
        else:
            cleaned_data['period'] = 0
        return cleaned_data
