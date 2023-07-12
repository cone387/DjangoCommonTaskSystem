from logging.handlers import RotatingFileHandler
from multiprocessing import Process, set_start_method
from django.db.models.signals import post_save
from django.utils import timezone
from django.utils.functional import cached_property
from datetime import datetime
from django_common_task_system.generic.choices import TaskClientStatus, ContainerStatus
from django_common_task_system.utils.algorithm import get_md5
from functools import cmp_to_key
from docker.models.containers import Container
from docker.errors import APIError
from django.db import models
import os
import subprocess
import logging
import locale
import docker


SYS_ENCODING = locale.getpreferredencoding()


def run_in_subprocess(cmd):
    logs = []
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if out:
        logs.append(out.decode(SYS_ENCODING))
    if err:
        logs.append(err.decode(SYS_ENCODING))
    return not err, logs


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
                column, op = k.split('__')
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

    def __get__(self, instance, owner):
        return self._meta.managers_map[self.manager.name]


class TaskClient(models.Model):
    container: Container = None
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
        verbose_name = verbose_name_plural = '系统进程'

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


def start_in_container(client: TaskClient):
    # pull image
    docker_client = docker.from_env()
    client.startup_status = TaskClientStatus.PULLING
    http_queue_url = client.settings_module['SUBSCRIPTION_ENGINE']['HttpSubscription']['subscription_url']
    command = "common-task-system-client --http-queue-url=%s" % http_queue_url
    try:
        container = docker_client.containers.create(client.container_image,
                                                    command=command,
                                                    name=client.container_name,
                                                    detach=False)
    except docker.errors.ImageNotFound:
        image, tag = client.container_image.split(':') if ':' in client.container_image else (
            client.container_image, None)
        for _ in range(3):
            try:
                docker_client.images.pull(image, tag=tag)
                break
            except APIError:
                pass
        else:
            raise RuntimeError('pull image failed: %s' % client.container_image)
        container = docker_client.containers.create(client.container_image,
                                                    command=command,
                                                    name=client.container_name, detach=True)
    client.container_id = container.short_id
    client.container = container
    container.start()
    docker_client.containers.get(container.short_id)
    client.container_status = container.status.capitalize()


def start_in_process(client: TaskClient):
    set_start_method('spawn', True)
    os.environ['TASK_CLIENT_SETTINGS_MODULE'] = client.settings_file.replace(
        os.getcwd(), '').replace(os.sep, '.').strip('.py')
    try:
        from task_system_client.main import start_task_system
    except ImportError:
        os.system('pip install common-task-system-client')
        try:
            from task_system_client.main import start_task_system
        except ImportError:
            raise RuntimeError('common-task-system-client install failed')
    from task_system_client.settings import logger
    logger.handlers.clear()
    if os.path.isfile(client.log_file):
        os.remove(client.log_file)
    handler = RotatingFileHandler(client.log_file, maxBytes=1024 * 1024 * 10, encoding='utf-8', backupCount=5)
    formatter = logging.Formatter('[%(asctime)s][%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    p = Process(target=start_task_system, daemon=True)
    p.start()
    client.client_id = p.pid
    client.startup_status = TaskClientStatus.SUCCEED
    if not p.is_alive():
        raise RuntimeError('client process start failed, process is not alive')


def start_client(client: TaskClient):
    import django
    django.setup()

    client.startup_status = TaskClientStatus.INIT
    try:
        if client.run_in_container:
            start_in_container(client)
        else:
            start_in_process(client)
        client.startup_status = TaskClientStatus.SUCCEED
    except Exception as e:
        client.startup_status = TaskClientStatus.FAILED
        client.startup_log = str(e)
