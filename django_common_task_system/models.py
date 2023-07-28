from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django_common_task_system.choices import (
    TaskStatus, ScheduleStatus, ScheduleCallbackStatus,
    ScheduleCallbackEvent, ScheduleQueueModule, TaskClientStatus, ContainerStatus, PermissionType, ExecuteStatus
)
from django_common_objects.models import CommonTag, CommonCategory
from django_common_objects import fields as common_fields
from datetime import datetime, timezone
from django.core.validators import ValidationError
from django_common_task_system.schedule.config import ScheduleConfig
from django_common_task_system.utils import foreign_key
from django.db.models.signals import post_save
from django.utils import timezone
from django.utils.functional import cached_property
from django_common_task_system.utils.algorithm import get_md5
from functools import cmp_to_key
from docker.models.containers import Container
import os
import re


UserModel = get_user_model()


def code_validator(value):
    if re.match(r'[a-zA-Z_-]+', value) is None:
        raise ValidationError('编码只能包含字母、数字、下划线和中划线')


class Task(models.Model):
    id = models.AutoField(primary_key=True)
    parent = models.ForeignKey('self', db_constraint=False, on_delete=models.CASCADE,
                               null=True, blank=True, verbose_name='父任务')
    name = models.CharField(max_length=100, verbose_name='任务名')
    category = models.ForeignKey(CommonCategory, db_constraint=False, on_delete=models.DO_NOTHING, verbose_name='类别')
    tags = models.ManyToManyField(CommonTag, blank=True, db_constraint=False, verbose_name='标签')
    description = models.TextField(blank=True, null=True, verbose_name='描述')
    config = common_fields.ConfigField(blank=True, null=True, default=dict, verbose_name='参数')
    status = common_fields.CharField(max_length=1, default=TaskStatus.ENABLE.value, verbose_name='状态',
                                     choices=TaskStatus.choices)
    # 更新最后一次操作的用户
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE, db_constraint=False, verbose_name='最后更新')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    @property
    def associated_tasks_ids(self):
        return foreign_key.get_related_object_ids(self)

    class Meta:
        verbose_name = verbose_name_plural = '任务中心'
        unique_together = (('name', 'parent'), )
        db_table = 'common_task'
        swappable = 'TASK_MODEL'

    def __str__(self):
        return self.name

    __repr__ = __str__


class ScheduleCallback(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, verbose_name='回调')
    description = models.TextField(blank=True, null=True, verbose_name='描述')
    trigger_event = common_fields.CharField(default=ScheduleCallbackEvent.DONE, choices=ScheduleCallbackEvent.choices,
                                            verbose_name='触发事件')
    status = common_fields.CharField(default=ScheduleCallbackStatus.ENABLE.value, verbose_name='状态',
                                     choices=ScheduleCallbackStatus.choices)
    config = common_fields.ConfigField(blank=True, null=True, verbose_name='参数')
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE, db_constraint=False, verbose_name='最后更新')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = verbose_name_plural = '计划回调'
        # unique_together = (('name', 'user'), )
        db_table = 'schedule_callback'

    def __str__(self):
        return self.name

    __repr__ = __str__


class Schedule(models.Model):
    id = models.AutoField(primary_key=True)
    task = models.ForeignKey(settings.TASK_MODEL, on_delete=models.CASCADE, db_constraint=False, verbose_name='任务')
    priority = models.IntegerField(default=0, verbose_name='优先级')
    next_schedule_time = models.DateTimeField(default=timezone.now, verbose_name='下次运行时间', db_index=True)
    schedule_start_time = models.DateTimeField(default=datetime.min, verbose_name='开始时间')
    schedule_end_time = models.DateTimeField(default=datetime.max, verbose_name='结束时间')
    config = common_fields.ConfigField(default=dict, verbose_name='参数')
    status = common_fields.CharField(default=ScheduleStatus.OPENING.value, verbose_name='状态',
                                     choices=ScheduleStatus.choices)
    is_strict = models.BooleanField(default=False, verbose_name='严格模式')
    callback = models.ForeignKey(ScheduleCallback, on_delete=models.SET_NULL,
                                 null=True, blank=True, db_constraint=False, verbose_name='回调')
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE, db_constraint=False, verbose_name='最后更新')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    # 这里的update_time不能使用auto_now，因为每次next_schedule_time更新时，都会更新update_time,
    # 这样会导致每次更新都会触发post_save且不知道啥时候更新了调度计划
    update_time = models.DateTimeField(default=timezone.now, verbose_name='更新时间')

    def generate_next_schedule(self):
        try:
            self.next_schedule_time = ScheduleConfig(config=self.config).get_next_time(self.next_schedule_time)
        except Exception as e:
            self.status = ScheduleStatus.ERROR.value
            self.save(update_fields=('status',))
            raise e
        if self.next_schedule_time > self.schedule_end_time:
            self.next_schedule_time = datetime.max
            self.status = ScheduleStatus.DONE.value
        self.save(update_fields=('next_schedule_time', 'status'))
        return self

    class Meta:
        verbose_name = verbose_name_plural = '计划中心'
        ordering = ('-priority', 'next_schedule_time')
        unique_together = ('task', 'status')
        swappable = 'SCHEDULE_MODEL'
        db_table = 'common_schedule'

    def __str__(self):
        return self.task.name

    __repr__ = __str__

    def __lt__(self, other):
        return self.priority < other.priority

    def __gt__(self, other):
        return self.priority > other.priority


class ScheduleQueue(models.Model):
    id = models.AutoField(primary_key=True, verbose_name='ID')
    name = models.CharField(max_length=100, verbose_name='队列名称', unique=True)
    code = models.CharField(max_length=100, verbose_name='队列编码', unique=True, validators=[code_validator])
    status = models.BooleanField(default=True, verbose_name='状态')
    module = models.CharField(max_length=100, verbose_name='队列类型',
                              default=ScheduleQueueModule.FIFO,
                              choices=ScheduleQueueModule.choices)
    config = models.JSONField(default=dict, verbose_name='配置', null=True, blank=True)
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE, db_constraint=False, verbose_name='最后更新')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = verbose_name_plural = '计划队列'
        db_table = 'schedule_queue'

    def __str__(self):
        return "%s(%s)" % (self.name, self.code)


class ScheduleProducer(models.Model):
    id = models.AutoField(primary_key=True, verbose_name='ID')
    name = models.CharField(max_length=100, verbose_name='生产名称')
    filters = models.JSONField(verbose_name='过滤器')
    lte_now = models.BooleanField(default=True, verbose_name='小于等于当前时间')
    queue = models.ForeignKey(ScheduleQueue, db_constraint=False, related_name='producers',
                              on_delete=models.CASCADE, verbose_name='队列')
    status = models.BooleanField(default=True, verbose_name='启用状态')
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE, db_constraint=False, verbose_name='最后更新')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = verbose_name_plural = '计划生产'
        db_table = 'schedule_producer'

    def __str__(self):
        return self.name


class ScheduleLog(models.Model):
    id = models.AutoField(primary_key=True)
    schedule = models.ForeignKey(settings.SCHEDULE_MODEL, db_constraint=False, on_delete=models.CASCADE,
                                 verbose_name='任务计划', related_name='logs')
    status = common_fields.CharField(verbose_name='运行状态', choices=ExecuteStatus.choices)
    queue = models.CharField(max_length=100, verbose_name='队列', default='opening')
    result = common_fields.ConfigField(blank=True, null=True, verbose_name='结果')
    schedule_time = models.DateTimeField(verbose_name='计划时间')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')

    class Meta:
        verbose_name = verbose_name_plural = '计划日志'
        ordering = ('-create_time',)
        db_table = 'schedule_log'
        swappable = 'SCHEDULE_LOG_MODEL'

    def __str__(self):
        return "schedule: %s, status: %s" % (self.schedule, self.status)

    __repr__ = __str__


class ScheduleQueuePermission(models.Model):
    id = models.AutoField(primary_key=True, verbose_name='ID')
    queue = models.ForeignKey(ScheduleQueue, db_constraint=False, on_delete=models.CASCADE, verbose_name='队列')
    type = models.CharField(max_length=1, verbose_name='类型',
                            default=PermissionType.IP_WHITE_LIST,
                            choices=PermissionType.choices)
    status = models.BooleanField(default=True, verbose_name='启用状态')
    config = models.JSONField(default=dict, verbose_name='配置', null=True, blank=True)
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE, db_constraint=False, verbose_name='最后更新')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = verbose_name_plural = '队列权限'
        unique_together = ('queue', 'status')
        db_table = 'schedule_queue_permission'

    def __str__(self):
        return self.queue.name

    __repr__ = __str__


class ExceptionReport(models.Model):
    id = models.AutoField(primary_key=True, verbose_name='ID')
    group = models.CharField(max_length=100, verbose_name='分组')
    ip = models.CharField(max_length=100, verbose_name='IP')
    content = models.TextField(verbose_name='内容')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')

    class Meta:
        db_table = 'exception_report'
        verbose_name = verbose_name_plural = '异常报告'
        ordering = ('-create_time',)

    def __str__(self):
        return "Exception(%s, %s)" % (self.ip, self.content[:50])

    __repr__ = __str__


class QuerySet(list):
    class Query:
        order_by = []
        select_related = False

    def __init__(self, seq, model):
        super().__init__(seq)
        self.query = self.Query
        self.model = model
        self.verbose_name = model._meta.verbose_name
        self.verbose_name_plural = model._meta.verbose_name_plural

    def filter(self, **kwargs) -> 'QuerySet':
        queryset = self
        for k, v in kwargs.items():
            try:
                column, op = k.split('__')
            except ValueError:
                column, op = k, 'exact'
            if op == 'in':
                queryset = self.__class__([x for x in queryset if getattr(x, column, '') in v], self.model)
            elif op == 'exact':
                queryset = self.__class__([x for x in queryset if getattr(x, column, '') == v], self.model)
        return queryset

    def order_by(self, *args) -> 'QuerySet':
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

    def select_related(self, *args) -> 'QuerySet':
        return self

    def count(self, value=None) -> int:
        return len(self)

    def delete(self):
        for x in self:
            x.delete()

    def get(self, **kwargs):
        for x in self:
            for k, v in kwargs.items():
                if getattr(x, k) != v:
                    break
            else:
                return x
        raise TaskClient.DoesNotExist

    def _clone(self):
        return self


class CustomManager(models.Manager, dict):

    def all(self):
        return QuerySet(dict.values(self), self.model)

    def get_queryset(self):
        return self.all()

    def get(self, pk, default=None):
        return dict.get(self, pk, default)

    def filter(self, **kwargs) -> 'QuerySet':
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

    objects = CustomManager()

    class Meta:
        managed = False
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


from enum import StrEnum


class MissingReason(StrEnum):
    SCHEDULE_EXCEPTION = 'SCHEDULE_EXCEPTION'
    EXCEED_MAX_RETRY_TIMES = 'EXCEED_MAX_RETRY_TIMES'


class MissingScheduleManager(CustomManager):

    def all(self):
        schedules = []
        for x in dict.values(self):
            schedules.extend(x)
        return QuerySet(schedules, self.model)


class MissingSchedule(models.Model):
    schedule = models.ForeignKey('Schedule', on_delete=models.DO_NOTHING, verbose_name='计划')
    reason: MissingReason = None

    objects = MissingScheduleManager()

    class Meta:
        managed = False
        verbose_name = verbose_name_plural = '缺失调度'

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        schedules = MissingSchedule.objects.setdefault(self.pk, [])
        schedules.append(self)

    def delete(self, using=None, keep_parents=False):
        schedules = MissingSchedule.objects.get(self.pk)
        schedules.remove(self)
        if not schedules:
            MissingSchedule.objects.pop(self.pk)
