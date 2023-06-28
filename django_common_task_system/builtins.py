from django_common_task_system.generic.choices import TaskCallbackEvent, TaskCallbackStatus, TaskScheduleStatus, \
    ScheduleQueueModule
from django_common_task_system.models import TaskScheduleCallback, \
    ConsumerPermission, TaskScheduleQueue, TaskScheduleProducer
from django_common_task_system.generic import builtins as generic_builtins, App


class BuiltinCallbacks(generic_builtins.BuiltinModels):
    model = TaskScheduleCallback
    model_unique_kwargs = ['name']

    def __init__(self, user):
        self.http_log_upload = self.model(
            name='Http日志上报',
            trigger_event=TaskCallbackEvent.DONE,
            status=TaskCallbackStatus.ENABLE.value,
            user=user,
        )
        super(BuiltinCallbacks, self).__init__()

    def init_object(self, obj):
        super(BuiltinCallbacks, self).init_object(obj)

    def initialize(self):
        super(BuiltinCallbacks, self).initialize()


class BuiltinQueues(generic_builtins.BaseBuiltinQueues):
    model = TaskScheduleQueue

    def __init__(self):
        self.opening = self.model(
            code=self.status_params_mapping[TaskScheduleStatus.OPENING.value],
            status=True,
            module=ScheduleQueueModule.QUEUE.value,
            name='已启用任务'
        )
        self.test = self.model(
            code=self.status_params_mapping[TaskScheduleStatus.TEST.value],
            status=True,
            module=ScheduleQueueModule.QUEUE.value,
            name='测试任务'
        )
        super(BuiltinQueues, self).__init__()


class BuiltinProducers(generic_builtins.BaseBuiltinProducers):
    model = TaskScheduleProducer

    def __init__(self, queues: BuiltinQueues):
        self.opening = self.model(
            queue=queues.opening,
            lte_now=True,
            filters={
                'status': TaskScheduleStatus.OPENING.value,
            },
            status=True,
            name='默认'
        )
        self.test = self.model(
            queue=queues.test,
            lte_now=True,
            filters={
                'status': TaskScheduleStatus.TEST.value,
            },
            status=True,
            name='测试'
        )

        super(BuiltinProducers, self).__init__()


class BuiltinConsumerPermissions(generic_builtins.BaseConsumerPermissions):
    model = ConsumerPermission


class Builtins(generic_builtins.BaseBuiltins):
    app = App.user_task

    def __init__(self):
        super(Builtins, self).__init__()
        self.queues = BuiltinQueues()
        self.callbacks = BuiltinCallbacks(self.user)
        self.producers = BuiltinProducers(self.queues)
        self.consumer_permissions = BuiltinConsumerPermissions()


builtins = Builtins()
builtins.initialize()
