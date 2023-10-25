import json
from typing import Optional, Callable
from django_common_task_system.choices import ConsumerStatus, ContainerStatus
from django_common_task_system import models
from docker.errors import APIError
from docker.models.containers import Container
from datetime import datetime
from django_common_task_system.cache_service import CacheState, MapKey, cache_agent
import traceback
import docker
import os


class ConsumerState(CacheState):

    def __init__(self, data):
        super(ConsumerState, self).__init__(key=MapKey('consumers'))
        self.consumer_id = data['consumer_id']
        self.machine = data['machine']
        self.container = data['container']
        self.process_id: str = data['process_id']
        assert len(self.consumer_id) == 36, 'consumer_id长度必须为36位'
        assert self.process_id.isdigit(), 'process_id必须为数字'
        assert self.machine['mac'], 'mac不能为空'
        self.update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    @classmethod
    def from_str(cls, data: str):
        data = json.loads(data)
        return cls(data)

    def pull(self):
        state = cache_agent.hget(self.key, self.consumer_id)
        if state:
            state = json.loads(state)
            for k, v in state.items():
                setattr(self, k, v)

    def delete(self):
        cache_agent.hdel(self.key, self.consumer_id)

    def push(self, **kwargs):
        try:
            cache_agent.hset(self.key, self.consumer_id, json.dumps(self))
        except Exception as e:
            print(e)


class ContainerSetting:
    def __init__(self, setting: dict):
        self.image = setting.get('image', 'cone387/common-task-system-client:latest')
        self.name = setting.get('name', 'common-task-system-client-%s' % datetime.now().strftime('%Y%m%d%H%M%S'))
        self.id = setting.get('id', '')
        self.ip = setting.get('ip', '')
        self.port = setting.get('port', '')
        self.status = ContainerStatus.NONE


class ConsumerProgram:
    def __init__(self, program: models.Program):
        self.program = program

    @property
    def is_running(self):
        return self.program.is_running

    @classmethod
    def load_from_container(cls, container: Container):
        kwargs = {x.split('=')[0].strip('-'): x.split('=')[1] for x in container.attrs['Args'] if '=' in x}
        consume_url = kwargs.pop('subscription-url', None)
        consumer = models.Consumer(
            consume_url=consume_url,
            consume_kwargs=kwargs,
            create_time=datetime.strptime(container.attrs['Created'].split('.')[0], "%Y-%m-%dT%H:%M:%S"),
        )
        # consumer.program = cls(model=consumer, container=container)
        consumer.save()

    def _run(self):
        program = self.program
        consumer = program.consumer
        # pull image
        docker_client = docker.from_env()
        setting = ContainerSetting(program.container)
        tmp_path = os.path.join(os.getcwd(), "tmp")
        if not os.path.exists(tmp_path):
            os.makedirs(tmp_path)
        machine_settings_file = os.path.join(tmp_path, "settings_%s.py" % consumer.id)
        container_settings_file = '/mnt/task-system-client-settings.py'
        command = ' '.join([
            'common-task-system-client',
            '--subscription-url="{consumer.consume_url}"',
            '--settings="{container_settings_file}"'
        ])
        try:
            self.container = docker_client.containers.create(
                setting.image, command=command, name=setting.name,
                volumes=[f"{machine_settings_file}:{container_settings_file}"],
                detach=True
            )
        except docker.errors.ImageNotFound:
            image, tag = setting.image.split(':') if ':' in setting.image else (
                setting.image, None)
            for _ in range(3):
                try:
                    docker_client.images.pull(image, tag=tag)
                    break
                except APIError:
                    pass
            else:
                raise RuntimeError('pull image failed: %s' % setting.image)
            self.container = docker_client.containers.create(
                setting.image, command=command, name=setting.name, detach=True)
        self.container.start()
        self.container = docker_client.containers.get(self.container.short_id)

    def run(self):
        program = self.program
        try:
            self._run()
            program.is_running = True
        except Exception as _:
            program.is_running = False
            program.startup_log = traceback.format_exc()
        program.save()

    def start_if_not_started(self) -> str:
        start_program: Callable[[], None] = getattr(self, 'start', None)
        if start_program is None:
            start_program = getattr(self, 'run', None)
        assert start_program, 'start or run method must be implemented'
        if self.is_running:
            print('%s already started, pid: %s' % (self, self.program))
        else:
            start_program()

    def read_log(self, page=0, page_size=1000):
        if self.program.is_running:
            # log = super(ConsumerProgram, self).read_log(page=page, page_size=page_size)
            log = "running"
        else:
            log = self.program.startup_log
        return log

    def stop(self):
        pass


def consume(model):
    program = ConsumerProgram(model)
    program.start_if_not_started()
    return program
