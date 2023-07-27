from . import models
from . import get_user_schedule_model, get_user_task_model
from django_common_task_system.generic import forms as generic_forms


UserTaskModel = get_user_task_model()
UserScheduleModel = get_user_schedule_model()


class TaskForm(generic_forms.TaskForm):

    class Meta(generic_forms.TaskForm.Meta):
        model = UserTaskModel


class TaskScheduleForm(generic_forms.ScheduleForm):

    class Meta(generic_forms.ScheduleForm.Meta):
        model = UserScheduleModel


class TaskScheduleQueueForm(generic_forms.ScheduleQueueForm):

    class Meta(generic_forms.ScheduleQueueForm.Meta):
        model = models.ScheduleQueue


class ScheduleProducerForm(generic_forms.ScheduleProducerForm):
    schedule_model = UserScheduleModel

    class Meta(generic_forms.ScheduleProducerForm.Meta):
        model = models.ScheduleProducer


class ConsumerPermissionForm(generic_forms.ConsumerPermissionForm):

    class Meta(generic_forms.ConsumerPermissionForm.Meta):
        model = models.ScheduleConsumerPermission
