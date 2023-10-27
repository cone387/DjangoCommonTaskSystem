import json
import traceback
from typing import Optional, Callable, List
from django_common_task_system.choices import ContainerStatus
from django_common_task_system import models
from docker.errors import APIError
from datetime import datetime
from django_common_task_system.serializers import ConsumerSerializer
from django_common_task_system.cache_service import CacheState, MapKey, cache_agent
import docker
import os


class ConsumerManager:
    key = MapKey('consumers')

    def __init__(self, key: MapKey):
        self.key = key

    def all(self) -> List[models.Consumer]:
        items = cache_agent.hgetall(self.key)
        if items:
            serializer = ConsumerSerializer(data=[json.loads(x) for x in items.values()], many=True)
            serializer.is_valid(raise_exception=True)
            consumers = serializer.save()
            return models.QuerySet(consumers, model=models.Consumer)
        return models.QuerySet([], model=models.Consumer)

    def get(self, consumer_id: str):
        state = cache_agent.hget(self.key, consumer_id)
        if state:
            return ConsumerState.from_str(state)
        return None

    def create(self, consumer):
        data = ConsumerSerializer(consumer).data
        cache_agent.hset(self.key, str(consumer.id), json.dumps(data))


class MachineManager:

    @staticmethod
    def all() -> List[models.Machine]:
        items = consumer_manager.all()
        machines = []
        macs = set()
        for item in items:
            machine = models.Machine(**item.machine)
            if machine.mac not in macs:
                machines.append(machine)
                macs.add(machine.mac)
        return machines


consumer_manager = ConsumerManager(MapKey('consumers)'))


class ConsumerState(CacheState):

    def __init__(self, data):
        super(ConsumerState, self).__init__(consumer_manager.key)
        # self.id = data['id']
        # self.machine = data['machine']
        # self.container = data['container']
        # self.process_id: int = data['process_id']
        # self.error: Optional[str] = data.get('error')
        # assert len(self.id) == 36, 'consumer_id长度必须为36位'
        # assert self.machine['mac'], 'mac不能为空'
        # self.active_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.consumer = data

    @classmethod
    def from_str(cls, data: str):
        data = json.loads(data)
        return cls(data)

    def pull(self):
        state = cache_agent.hget(self.key, self.id)
        if state:
            state = json.loads(state)
            for k, v in state.items():
                setattr(self, k, v)

    def delete(self):
        cache_agent.hdel(self.key, self.id)

    def push(self, **kwargs):
        try:
            cache_agent.hset(self.key, self.id, json.dumps(self))
        except Exception as e:
            print(e)


class ConsumerContainer:
    default_image = 'cone387/common-task-system-client:latest'
    default_name = 'common-task-system-client-'

    def __init__(self, container: dict):
        self.image = container.get('image', self.default_image)
        self.name = container.get('name', f'{self.default_name}-%s' % datetime.now().strftime('%Y%m%d%H%M%S'))
        self.id = container.get('id', '')
        self.ip = container.get('ip', '')
        self.port = container.get('port', '')
        self.status = ContainerStatus.NONE


class ConsumerProgram:
    def __init__(self, consumer: models.Consumer):
        self.consumer = consumer

    def run(self):
        consumer = self.consumer
        # pull image
        docker_client = docker.from_env()
        setting = ConsumerContainer(consumer.container)
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
            container = docker_client.containers.create(
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
            container = docker_client.containers.create(
                setting.image, command=command, name=setting.name, detach=True)
        container.start()
        # self.container = docker_client.containers.get(self.container.short_id)

    def start_if_not_started(self):
        start_program: Callable[[], None] = getattr(self, 'start', None)
        if start_program is None:
            start_program = getattr(self, 'run', None)
        assert start_program, 'start or run method must be implemented'
        try:
            start_program()
        except Exception:
            self.consumer.error = traceback.format_exc()
        consumer_manager.create(self.consumer)


def consume(model):
    program = ConsumerProgram(model)
    program.start_if_not_started()
    return program
