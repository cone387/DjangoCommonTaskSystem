from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django_common_task_system.choices import (
    TaskStatus, ScheduleStatus, ScheduleCallbackStatus,
    ScheduleCallbackEvent, ScheduleQueueModule, TaskClientStatus, ClientEngineType,
    PermissionType, ExecuteStatus, ScheduleExceptionReason
)
from django_common_objects.models import CommonTag, CommonCategory
from django_common_objects import fields as common_fields
from datetime import datetime, timezone
from django.core.validators import ValidationError
from django_common_task_system.schedule.config import ScheduleConfig
from django_common_task_system.utils import foreign_key
from django_common_task_system.schedule import util as schedule_util
from django.db.models.signals import post_save, post_delete
from django.utils import timezone
from django.utils.functional import cached_property
from django_common_task_system.utils.algorithm import get_md5
from functools import cmp_to_key
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


class AbstractSchedule(models.Model):
    id = models.AutoField(primary_key=True)
    task = models.OneToOneField(settings.TASK_MODEL, on_delete=models.CASCADE,
                                db_constraint=False, verbose_name='任务')
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
    preserve_log = models.BooleanField(default=True, verbose_name='保留日志')
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE, db_constraint=False, verbose_name='最后更新')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    # 这里的update_time不能使用auto_now，因为每次next_schedule_time更新时，都会更新update_time,
    # 这样会导致每次更新都会触发post_save且不知道啥时候更新了调度计划
    update_time = models.DateTimeField(default=timezone.now, verbose_name='更新时间')

    class Meta:
        verbose_name = verbose_name_plural = '计划中心'
        ordering = ('-priority', 'next_schedule_time')
        abstract = True

    def __str__(self):
        return self.task.name

    __repr__ = __str__

    def __lt__(self, other):
        return self.priority < other.priority

    def __gt__(self, other):
        return self.priority > other.priority


class Schedule(AbstractSchedule):

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

    class Meta(AbstractSchedule.Meta):
        swappable = 'SCHEDULE_MODEL'
        db_table = 'common_schedule'


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
    client = models.CharField(max_length=100, verbose_name='客户端')
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
            v = str(v)
            try:
                column, op = k.rsplit('__', 1)
            except ValueError:
                column, op = k, 'exact'

            def get_attr(x):
                for attr in column.split('__'):
                    x = getattr(x, attr, '')
                return str(x)

            if op == 'in':
                queryset = self.__class__([x for x in queryset if get_attr(x) in v], self.model)
            elif op == 'exact':
                queryset = self.__class__([x for x in queryset if get_attr(x) == v], self.model)
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

    def select_related(self, *_) -> 'QuerySet':
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
        raise self.model.DoesNotExist

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

    def none(self):
        return QuerySet([], self.model)

    def count(self):
        return len(self)

    def __get__(self, instance, owner):
        return self._meta.managers_map[self.manager.name]


class ClientEngine:
    def __init__(self, engine_settings: dict):
        self.engine_settings = engine_settings

    def __setattr__(self, key, value):
        if key == 'engine_settings':
            super().__setattr__(key, value)
            return
        o = self.engine_settings.get(key)
        if o is not None and o != value:
            self.engine_settings[key] = value
        super().__setattr__(key, value)


class DockerEngine(ClientEngine):
    def __init__(self, engine_settings: dict):
        super().__init__(engine_settings)
        self.container_id = engine_settings.get('container_id')
        self.container_name = engine_settings.get(
            'container_name') or 'common-task-system-client-%s' % datetime.now().strftime("%Y%m%d%H%M%S")
        self.image = engine_settings.get('image') or 'cone387/common-task-system-client:latest'
        self.container_ip = engine_settings.get('container_ip')
        self.container_port = engine_settings.get('container_port')
        self.container_status = engine_settings.get('container_status')
        self.container_create_time = engine_settings.get('container_create_time')


class ProcessEngine(ClientEngine):
    pass


class TaskClient(models.Model):
    # 两种运行模式: 容器模式，进程模式
    runner = None

    client_id = models.IntegerField(verbose_name='客户端ID', primary_key=True, default=0)
    machine_name = models.CharField(max_length=100, verbose_name='机器名', default='本机')
    machine_ip = models.GenericIPAddressField(max_length=100, verbose_name='机器IP', default='127.0.0.1')
    group = models.CharField(max_length=100, verbose_name='分组', default='默认')
    subscription_url = models.CharField(max_length=200, verbose_name='订阅地址')
    subscription_kwargs = models.JSONField(verbose_name='订阅参数', default=dict)
    engine_type = models.CharField(max_length=100, verbose_name='运行引擎', choices=ClientEngineType.choices,
                                   default=ClientEngineType.DOCKER)
    engine_settings = models.JSONField(verbose_name='引擎设置', default=dict)
    env = models.CharField(max_length=500, verbose_name='环境变量', blank=True, null=True)
    startup_status = models.CharField(max_length=500, choices=TaskClientStatus.choices,
                                      verbose_name='启动结果', default=TaskClientStatus.RUNNING)
    startup_log = models.CharField(max_length=2000, null=True, blank=True)
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    settings = models.JSONField(verbose_name='客户端设置', default=dict)

    objects = CustomManager()

    @property
    def engine(self):
        if self.engine_type == ClientEngineType.DOCKER:
            return DockerEngine(self.engine_settings)
        elif self.engine_type == ClientEngineType.PROCESS:
            return ProcessEngine(self.engine_settings)
        else:
            raise ValueError("Invalid engine_type: %s" % self.engine_type)

    class Meta:
        managed = False
        verbose_name = verbose_name_plural = '客户端管理'

    def __str__(self):
        return str(self.client_id)

    @cached_property
    def fp(self):
        return get_md5("%s" % self.runner.id if self.runner else self.client_id)

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
        TaskClient.objects[self.client_id] = self
        if self.runner is None:
            self.create_time = timezone.now()
            post_save.send(
                sender=TaskClient,
                instance=self,
                created=True,
                update_fields=update_fields,
                raw=False,
                using=using,
            )

    def delete(self, using=None, keep_parents=False):
        if self.runner is not None:
            self.runner.stop()
        TaskClient.objects.pop(self.client_id, None)


class ExceptionScheduleManager(CustomManager):

    def all(self):
        raise NotImplementedError

    def get(self, pk, default=None):
        queryset = super().get(pk, default)
        return queryset[0] if queryset else default

    def records_to_queryset(self, records, schedule, queue, reason):
        mapping = {}
        for x in records:
            mapping.setdefault(x['schedule_id'], []).append(x)
        if schedule is None:
            schedules = Schedule.objects.filter(pk__in=mapping.keys()).select_related('task')
        else:
            schedules = [schedule]
        queryset = []
        for x in schedules:
            for e in mapping.get(x.pk, []):
                exception = ExceptionSchedule(
                    id=x.pk,
                    schedule_time=e['schedule_time'],
                    queue=queue,
                    reason=reason,
                    schedule=x,
                )
                queryset.append(exception)
        return QuerySet(queryset, self.model)

    def get_retry_queryset(self, queue: str, schedule_pk) -> QuerySet:
        records = schedule_util.get_retryable_records(queue)
        if schedule_pk:
            schedule = Schedule.objects.get(id=schedule_pk)
            records = records.filter(schedule=schedule)
        else:
            schedule = None
        return self.records_to_queryset(records, schedule, queue, "retry")

    def get_exception_queryset(self, queue: str, reason, schedule_pk) -> QuerySet:
        if schedule_pk:
            schedule = Schedule.objects.get(id=schedule_pk)
        else:
            schedule = None
        if reason == ScheduleExceptionReason.SCHEDULE_LOG_NOT_FOUND:
            queryset = self.get_missing_queryset(queue, schedule)
        elif reason == ScheduleExceptionReason.MAXIMUM_RETRIES_EXCEEDED:
            queryset = self.get_maximum_retries_exceeded_queryset(queue, schedule)
        elif reason == ScheduleExceptionReason.FAILED_DIRECTLY:
            queryset = self.get_failed_directly_queryset(queue, schedule)
        else:
            raise ValueError("reason %s is not supported" % reason)
        return queryset

    def get_maximum_retries_exceeded_queryset(self, queue: str, schedule: Schedule):
        records = schedule_util.get_maximum_retries_exceeded_records(schedule)
        if schedule is not None:
            records = records.filter(schedule=schedule.id)
        return self.records_to_queryset(records, schedule, queue, ScheduleExceptionReason.MAXIMUM_RETRIES_EXCEEDED)

    def get_failed_directly_queryset(self, queue: str, schedule: Schedule):
        records = schedule_util.get_failed_directly_records(queue)
        if schedule is not None:
            records = records.filter(schedule=schedule.id)
        return self.records_to_queryset(records, schedule, queue, ScheduleExceptionReason.FAILED_DIRECTLY)

    def get_missing_queryset(self, queue, schedule: Schedule):
        if schedule is None or not schedule.is_strict:
            return self.none()
        missing_schedule_records = schedule_util.get_log_missing_records(queue, schedule)
        schedules = []
        for schedule_time in missing_schedule_records:
            missing = ExceptionSchedule(
                id=schedule.pk,
                queue=queue,
                schedule=schedule,
                schedule_time=schedule_time,
                reason=ScheduleExceptionReason.SCHEDULE_LOG_NOT_FOUND
            )
            schedules.append(missing)
        return QuerySet(schedules, self.model)


class ExceptionSchedule(models.Model):
    id = models.IntegerField(verbose_name='计划ID', primary_key=True)
    schedule = models.ForeignKey(settings.SCHEDULE_MODEL, on_delete=models.DO_NOTHING,
                                 db_constraint=False, verbose_name='计划')
    schedule_time = models.DateTimeField(verbose_name='计划时间')
    queue = models.CharField(max_length=100, verbose_name='队列')
    reason = models.CharField(max_length=100, verbose_name='异常原因',
                              default=ScheduleExceptionReason.FAILED_DIRECTLY,
                              choices=ScheduleExceptionReason.choices)

    objects = ExceptionScheduleManager()

    def __str__(self):
        self.schedule: Schedule
        return self.schedule.task.name

    class Meta:
        managed = False
        verbose_name = verbose_name_plural = '异常的计划'
        ordering = ('id', '-schedule_time',)

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        schedules = ExceptionSchedule.objects.setdefault(self.pk, [])
        schedules.append(self)

    def delete(self, using=None, keep_parents=False):
        super(ExceptionSchedule, self).delete()
        schedules = ExceptionSchedule.objects.get(self.pk)
        schedules.remove(self)
        if not schedules:
            ExceptionSchedule.objects.pop(self.pk)
        return 1, 1


class RetrySchedule(ExceptionSchedule):

    class Meta:
        managed = False
        verbose_name = verbose_name_plural = '待重试计划'
        ordering = ('id', '-schedule_time',)


class Overview(models.Model):
    name = models.CharField(max_length=100, verbose_name='名称')
    state = models.CharField(max_length=100, verbose_name='状态')
    action = models.CharField(max_length=100, verbose_name='操作')

    objects = CustomManager()

    class Meta:
        managed = False
        verbose_name = verbose_name_plural = '系统总览'
        ordering = ('name',)
