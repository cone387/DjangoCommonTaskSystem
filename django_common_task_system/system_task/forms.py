from . import models
from django import forms


class SystemTaskForm(forms.ModelForm):
    queue = forms.ModelChoiceField(
        queryset=models.SystemScheduleQueue.objects.all(),
        required=False,
        label='队列',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        super(SystemTaskForm, self).__init__(**kwargs)
        if self.instance.id:
            self.fields['name'].widget.attrs['readonly'] = True

    class Meta:
        model = models.SystemTask
        fields = '__all__'
