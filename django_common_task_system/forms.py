from . import models
from . import get_task_schedule_model, get_task_model
from django_common_task_system.generic import forms as generic_forms


TaskModel = get_task_model()
ScheduleModel = get_task_schedule_model()


class TaskForm(generic_forms.TaskForm):

    class Meta(generic_forms.TaskForm.Meta):
        model = TaskModel


class TaskScheduleForm(generic_forms.TaskScheduleForm):

    class Meta(generic_forms.TaskScheduleForm.Meta):
        model = ScheduleModel


class TaskScheduleQueueForm(generic_forms.TaskScheduleQueueForm):

    class Meta(generic_forms.TaskScheduleQueueForm.Meta):
        model = models.TaskScheduleQueue


class TaskScheduleProducerForm(generic_forms.TaskScheduleProducerForm):
    schedule_model = ScheduleModel

    class Meta(generic_forms.TaskScheduleProducerForm.Meta):
        model = models.TaskScheduleProducer


class ConsumerPermissionForm(generic_forms.ConsumerPermissionForm):

    class Meta(generic_forms.ConsumerPermissionForm.Meta):
        model = models.ConsumerPermission
