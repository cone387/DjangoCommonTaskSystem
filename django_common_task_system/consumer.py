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
    heartbeat_key = MapKey('consumers:heartbeat')

    def __init__(self, key: MapKey):
        self.key = key

    def all(self) -> List[models.Consumer]:
        items = cache_agent.hgetall(self.key)
        if items:
            consumers = [models.Consumer(**json.loads(x)) for x in items.values()]
            return models.QuerySet(consumers, model=models.Consumer)
        return models.QuerySet([], model=models.Consumer)

    def get(self, consumer_id: str):
        item = cache_agent.hget(self.key, consumer_id)
        if item:
            return models.Consumer(**json.loads(item))
        return None

    def exists(self, consumer_id: str):
        return cache_agent.hexists(self.key, consumer_id)

    def create(self, consumer):
        data = ConsumerSerializer(consumer).data
        cache_agent.hset(self.key, str(consumer.id), json.dumps(data))
        return consumer

    def delete(self, consumer_id):
        return cache_agent.hdel(self.key, consumer_id)

    def heartbeat(self, consumer_id):
        cache_agent.hset(self.heartbeat_key, consumer_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    def get_heartbeat(self, consumer_id):
        return cache_agent.hget(self.heartbeat_key, consumer_id)

    def in_waitlist(self, consumer_id) -> bool:
        return cache_agent.exists(consumer_id)

    def join_waitlist(self, consumer_id):
        cache_agent.set(consumer_id, 1, expire=60)

    def write_log(self, consumer_id, log: str):
        cache_agent.set(f'logs:{consumer_id}', log, expire=60 * 60)

    def read_log(self, consumer_id) -> Optional[str]:
        return cache_agent.get(f'logs:{consumer_id}') or ''


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

        commands = [
            '/usr/local/bin/common-task-system-client',
            f'--subscription-url="{consumer.consume_url}"',
        ]
        volumes = ["/var/run/docker.sock:/var/run/docker.sock"]

        if consumer.settings:
            tmp_path = os.path.join(os.getcwd(), "tmp")
            if not os.path.exists(tmp_path):
                os.makedirs(tmp_path)
            machine_settings_file = os.path.join(tmp_path, "settings_%s.py" % consumer.id[:8])
            container_settings_file = '/etc/task-system-client/settings.py'
            with open(machine_settings_file, 'w', encoding='utf-8') as f:
                f.write(consumer.settings)
            commands.append(f'--settings={container_settings_file}')
            volumes.append(f'{machine_settings_file}:{container_settings_file}')
        command = ' '.join(commands)
        try:
            container = docker_client.containers.create(
                setting.image, command=command, name=setting.name,
                volumes=volumes, environment={"TASK_CLIENT_ID": consumer.id},
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
        container = docker_client.containers.get(container.short_id)
        self.consumer.container['id'] = container.short_id

    def start_if_not_started(self):
        start_program: Callable[[], None] = getattr(self, 'start', None)
        if start_program is None:
            start_program = getattr(self, 'run', None)
        assert start_program, 'start or run method must be implemented'
        start_program()
        # try:
        #     start_program()
        # except Exception:
        #     self.consumer.error = traceback.format_exc()
        consumer_manager.create(self.consumer)


def consume(model):
    program = ConsumerProgram(model)
    program.start_if_not_started()
    return program
