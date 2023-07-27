from django.contrib.auth import get_user_model
from django.db import models
from django_common_task_system.generic.choices import TaskStatus, TaskScheduleStatus, TaskCallbackStatus, \
    TaskCallbackEvent, ScheduleQueueModule, ConsumerPermissionType, TaskClientStatus, ContainerStatus
from django_common_objects.models import CommonTag, CommonCategory
from django_common_objects import fields as common_fields
from django_common_task_system.generic import ScheduleConfig
from datetime import datetime
import re
from django.core.validators import ValidationError
from django_common_task_system.utils import foreign_key
from django.db.models.signals import post_save
from django.utils import timezone
from django.utils.functional import cached_property
from django_common_task_system.utils.algorithm import get_md5
from functools import cmp_to_key
from docker.models.containers import Container
from django_common_task_system.generic.app import App
import os


UserModel = get_user_model()


def code_validator(value):
    if re.match(r'[a-zA-Z_-]+', value) is None:
        raise ValidationError('编码只能包含字母、数字、下划线和中划线')


class AbstractTask(models.Model):
    id = models.AutoField(primary_key=True)
    parent = models.ForeignKey('self', db_constraint=False, on_delete=models.DO_NOTHING,
                               null=True, blank=True, verbose_name='父任务')
    name = models.CharField(max_length=100, verbose_name='任务名')
    category = models.ForeignKey(CommonCategory, db_constraint=False, on_delete=models.DO_NOTHING, verbose_name='类别')
    tags = models.ManyToManyField(CommonTag, blank=True, db_constraint=False, verbose_name='标签')
    description = models.TextField(blank=True, null=True, verbose_name='描述')
    config = common_fields.ConfigField(blank=True, null=True, verbose_name='参数')
    status = common_fields.CharField(max_length=1, default=TaskStatus.ENABLE.value, verbose_name='状态',
                                     choices=TaskStatus.choices)
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE, db_constraint=False, verbose_name='用户')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    @property
    def associated_tasks_ids(self):
        return foreign_key.get_related_object_ids(self)

    class Meta:
        verbose_name = verbose_name_plural = '任务中心'
        unique_together = ('name', 'user', 'parent')
        abstract = True

    def __str__(self):
        return self.name

    __repr__ = __str__


class AbstractScheduleCallback(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, verbose_name='回调')
    description = models.TextField(blank=True, null=True, verbose_name='描述')
    trigger_event = common_fields.CharField(default=TaskCallbackEvent.DONE, choices=TaskCallbackEvent.choices,
                                            verbose_name='触发事件')
    status = common_fields.CharField(default=TaskCallbackStatus.ENABLE.value, verbose_name='状态',
                                     choices=TaskCallbackStatus.choices)
    config = common_fields.ConfigField(blank=True, null=True, verbose_name='参数')
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE, db_constraint=False, verbose_name='用户')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = verbose_name_plural = '任务回调'
        # unique_together = (('name', 'user'), )
        db_table = 'schedule_callback'
        abstract = True

    def __str__(self):
        return self.name

    __repr__ = __str__


class AbstractTaskSchedule(models.Model):
    id = models.AutoField(primary_key=True)
    task = models.ForeignKey(AbstractTask, on_delete=models.CASCADE, db_constraint=False, verbose_name='任务')
    priority = models.IntegerField(default=0, verbose_name='优先级')
    next_schedule_time = models.DateTimeField(default=timezone.now, verbose_name='下次运行时间', db_index=True)
    schedule_start_time = models.DateTimeField(default=datetime.min, verbose_name='开始时间')
    schedule_end_time = models.DateTimeField(default=datetime.max, verbose_name='结束时间')
    config = common_fields.ConfigField(default=dict, verbose_name='参数')
    status = common_fields.CharField(default=TaskScheduleStatus.OPENING.value, verbose_name='状态',
                                     choices=TaskScheduleStatus.choices)
    strict_mode = models.BooleanField(default=False, verbose_name='严格模式')
    callback = models.ForeignKey(AbstractScheduleCallback, on_delete=models.CASCADE,
                                 null=True, blank=True, db_constraint=False, verbose_name='回调')
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE, db_constraint=False, verbose_name='用户')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    def generate_next_schedule(self):
        try:
            self.next_schedule_time = ScheduleConfig(config=self.config).get_next_time(self.next_schedule_time)
        except Exception as e:
            self.status = TaskScheduleStatus.ERROR.value
            self.save(update_fields=('status',))
            raise e
        if self.next_schedule_time > self.schedule_end_time:
            self.next_schedule_time = datetime.max
            self.status = TaskScheduleStatus.DONE.value
        self.save(update_fields=('next_schedule_time', 'status'))
        return self

    class Meta:
        verbose_name = verbose_name_plural = '任务计划'
        ordering = ('-priority', 'next_schedule_time')
        unique_together = ('task', 'status', 'user')
        abstract = True

    def __str__(self):
        return self.task.name

    __repr__ = __str__

    def __lt__(self, other):
        return self.priority < other.priority

    def __gt__(self, other):
        return self.priority > other.priority


class AbstractTaskScheduleQueue(models.Model):
    id = models.AutoField(primary_key=True, verbose_name='ID')
    name = models.CharField(max_length=100, verbose_name='队列名称', unique=True)
    code = models.CharField(max_length=100, verbose_name='队列编码', unique=True, validators=[code_validator])
    status = models.BooleanField(default=True, verbose_name='状态')
    module = models.CharField(max_length=100, verbose_name='队列类型',
                              default=ScheduleQueueModule.QUEUE,
                              choices=ScheduleQueueModule.choices)
    config = models.JSONField(default=dict, verbose_name='配置', null=True, blank=True)
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = verbose_name_plural = '任务队列'
        db_table = 'schedule_queue'
        abstract = True

    def __str__(self):
        return "%s(%s)" % (self.name, self.code)


class AbstractTaskScheduleProducer(models.Model):
    id = models.AutoField(primary_key=True, verbose_name='ID')
    name = models.CharField(max_length=100, verbose_name='生产名称')
    filters = models.JSONField(verbose_name='过滤器')
    lte_now = models.BooleanField(default=True, verbose_name='小于等于当前时间')
    queue = models.ForeignKey(AbstractTaskScheduleQueue, db_constraint=False, related_name='producers',
                              on_delete=models.CASCADE, verbose_name='队列')
    status = models.BooleanField(default=True, verbose_name='启用状态')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = verbose_name_plural = '计划生产'
        db_table = 'schedule_producer'
        abstract = True

    def __str__(self):
        return self.name


class AbstractTaskScheduleLog(models.Model):
    id = models.AutoField(primary_key=True)
    schedule = models.ForeignKey(AbstractTaskSchedule, db_constraint=False, on_delete=models.CASCADE,
                                 verbose_name='任务计划')
    status = common_fields.CharField(verbose_name='运行状态')
    queue = models.CharField(max_length=100, verbose_name='队列', default='opening')
    result = common_fields.ConfigField(blank=True, null=True, verbose_name='结果')
    schedule_time = models.DateTimeField(verbose_name='计划时间')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')

    class Meta:
        verbose_name = verbose_name_plural = '任务日志'
        ordering = ('-create_time',)
        abstract = True

    def __str__(self):
        return "schedule: %s, status: %s" % (self.schedule, self.status)

    __repr__ = __str__


class AbstractConsumerPermission(models.Model):
    id = models.AutoField(primary_key=True, verbose_name='ID')
    producer = models.ForeignKey(AbstractTaskScheduleProducer, db_constraint=False,
                                 on_delete=models.CASCADE, verbose_name='生产者')
    type = models.CharField(max_length=1, verbose_name='类型',
                            default=ConsumerPermissionType.IP_WHITE_LIST,
                            choices=ConsumerPermissionType.choices)
    status = models.BooleanField(default=True, verbose_name='启用状态')
    config = models.JSONField(default=dict, verbose_name='配置', null=True, blank=True)
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = verbose_name_plural = '消费权限'
        # unique_together = ('producer', 'status')
        db_table = 'schedule_consumer_permission'
        abstract = True

    def __str__(self):
        return self.producer.name

    __repr__ = __str__


class AbstractExceptionReport(models.Model):
    id = models.AutoField(primary_key=True, verbose_name='ID')
    group = models.CharField(max_length=100, verbose_name='分组')
    ip = models.CharField(max_length=100, verbose_name='IP')
    content = models.TextField(verbose_name='内容')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')

    class Meta:
        db_table = 'exception_report'
        verbose_name = verbose_name_plural = '异常报告'
        ordering = ('-create_time',)
        abstract = True

    def __str__(self):
        return "Exception(%s, %s)" % (self.ip, self.content[:50])

    __repr__ = __str__


class TaskClientManager(models.Manager, dict):

    class QuerySet(list):
        class Query:
            order_by = []
            select_related = False

        def __init__(self, seq):
            super().__init__(seq)
            self.verbose_name = 'TaskClient'
            self.verbose_name_plural = 'TaskClient'
            self.query = self.Query
            self.model = TaskClient

        def filter(self, pk__in=None, **kwargs) -> 'TaskClientManager.QuerySet':
            if pk__in:
                return self.__class__(x for x in self if str(x.pk) in pk__in)
            queryset = self
            for k, v in kwargs.items():
                try:
                    column, op = k.split('__')
                except ValueError:
                    column, op = k, 'exact'
                if op == 'in':
                    queryset = self.__class__(x for x in queryset if getattr(x, column, '') in v)
                elif op == 'exact':
                    queryset = self.__class__(x for x in queryset if getattr(x, column, '') == v)
            return queryset

        def order_by(self, *args) -> 'TaskClientManager.QuerySet':
            def custom_sort(x, y):
                for arg in args:
                    if arg.startswith('-'):
                        arg = arg[1:]
                        reverse = True
                    else:
                        reverse = False
                    if getattr(x, arg) > getattr(y, arg):
                        return -1 if reverse else 1
                    elif getattr(x, arg) < getattr(y, arg):
                        return 1 if reverse else -1
                return 0
            self.sort(key=cmp_to_key(custom_sort))
            return self

        def count(self, value=None) -> int:
            return len(self)

        def delete(self):
            for x in self:
                x.delete()

        def get(self, **kwargs) -> 'TaskClient':
            for x in self:
                for k, v in kwargs.items():
                    if getattr(x, k) != v:
                        break
                else:
                    return x
            raise TaskClient.DoesNotExist

        def _clone(self):
            return self

    def all(self):
        return self.QuerySet(dict.values(self))

    def get(self, client_id, default=None) -> 'TaskClient':
        return dict.get(self, client_id, default)

    def filter(self, **kwargs) -> 'TaskClientManager.QuerySet':
        return self.all().filter(**kwargs)

    def __get__(self, instance, owner):
        return self._meta.managers_map[self.manager.name]


class TaskClient(models.Model):
    container: Container = None
    group = models.CharField(max_length=100, verbose_name='分组')
    subscription_url = models.CharField(max_length=200, verbose_name='订阅地址')
    subscription_kwargs = models.JSONField(verbose_name='订阅参数', default=dict)
    client_id = models.IntegerField(verbose_name='客户端ID', primary_key=True, default=0)
    process_id = models.PositiveIntegerField(verbose_name='进程ID', null=True, blank=True)
    container_id = models.CharField(max_length=100, verbose_name='容器ID', blank=True, null=True)
    container_name = models.CharField(max_length=100, verbose_name='容器名称', blank=True, null=True)
    container_image = models.CharField(max_length=100, verbose_name='容器镜像', blank=True, null=True)
    container_status = models.CharField(choices=ContainerStatus.choices, default=ContainerStatus.NONE,
                                        max_length=20, verbose_name='容器状态')
    run_in_container = models.BooleanField(default=True, verbose_name='是否在容器中运行')
    env = models.CharField(max_length=500, verbose_name='环境变量', blank=True, null=True)
    startup_status = models.CharField(max_length=500, choices=TaskClientStatus.choices,
                                      verbose_name='启动结果', default=TaskClientStatus.SUCCEED)
    settings = models.TextField(verbose_name='配置', blank=True, null=True)
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    startup_log = models.CharField(max_length=2000, null=True, blank=True)

    settings_module = {}

    objects = TaskClientManager()

    class Meta:
        managed = False
        app_label = App.system_task.split('.')[1] if App.system_task.is_installed else App.user_task
        verbose_name = verbose_name_plural = '客户端'

    def __str__(self):
        return str(self.client_id)

    @cached_property
    def fp(self):
        return get_md5("%s-%s" % (self.container_id, self.process_id))

    @cached_property
    def settings_file(self):
        tmp_path = os.path.join(os.getcwd(), "tmp")
        if not os.path.exists(tmp_path):
            os.makedirs(tmp_path)
        return os.path.join(tmp_path, "settings_%s.py" % self.fp)

    @cached_property
    def log_file(self):
        log_path = os.path.join(os.getcwd(), "logs")
        if not os.path.exists(log_path):
            os.makedirs(log_path)
        return os.path.join(log_path, "log_%s.log" % self.fp)

    def save(
            self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        if not self.client_id:
            self.client_id = max([c.client_id for c in TaskClient.objects.all()]) + 1 if TaskClient.objects else 1
        if self.group is None:
            self.group = self.__class__.__name__
        TaskClient.objects[self.client_id] = self
        if self.container is None:
            self.create_time = timezone.now()
            post_save.send(
                sender=TaskClient,
                instance=self,
                created=True,
                update_fields=update_fields,
                raw=False,
                using=using,
            )
        else:
            self.create_time = datetime.strptime(self.container.attrs['Created'].split('.')[0], "%Y-%m-%dT%H:%M:%S")

    def delete(self, using=None, keep_parents=False):
        if self.container is not None:
            self.container.stop()
            self.container.remove()
        TaskClient.objects.pop(self.client_id)
