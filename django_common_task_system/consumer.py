import json
import queue as python_queue
import traceback
from typing import Optional, Callable, List
from django_common_task_system.builtins import builtins
from django_common_task_system.choices import ContainerStatus
from django_common_task_system import models
from docker.errors import APIError
from datetime import datetime
from django_common_task_system.serializers import ConsumerSerializer
from django_common_task_system.cache_service import MapKey, cache_agent
import docker
import os


class ConsumerManager:
    heartbeat_key = MapKey('consumers:heartbeat')
    _mapping = {}

    @classmethod
    def generate_key(cls, queue_code: str, consumer_id: str = None):
        if consumer_id:
            return f'{queue_code}:{consumer_id}'
        return f'consumers:{queue_code}'

    def __new__(cls, queue_code: str):
        key = cls.generate_key(queue_code)
        if key not in cls._mapping:
            cls._mapping[key] = super().__new__(cls)
        return cls._mapping[key]

    def __init__(self, queue_code: str):
        schedule_queue = builtins.schedule_queues.get(queue_code)
        if schedule_queue is None:
            raise ValueError('queue(%s)不存在' % queue_code)
        self.key = self.generate_key(queue_code)
        self.schedule_queue: models.ScheduleQueue = schedule_queue
        self.queue: python_queue.Queue = schedule_queue.queue

    def consumers(self) -> List[models.Consumer]:
        items = cache_agent.hgetall(self.key)
        if items:
            consumers = [models.Consumer(**json.loads(x)) for x in items.values()]
            return models.QuerySet(consumers, model=models.Consumer)
        return models.QuerySet([], model=models.Consumer)

    @staticmethod
    def all_consumers() -> List[models.Consumer]:
        consumers = models.QuerySet([], model=models.Consumer)
        for manager in ConsumerManager.all_managers():
            consumers.extend(manager.consumers())
        return consumers

    @staticmethod
    def all_managers() -> List['ConsumerManager']:
        managers = []
        for key in cache_agent.filter('consumers:'):
            queue = key.split(':')[1]
            if queue == 'heartbeat':
                continue
            manager = ConsumerManager(queue)
            managers.append(manager)
        return managers

    @staticmethod
    def get_consumer(consumer_id):
        for manager in ConsumerManager.all_managers():
            consumer = manager.get(consumer_id)
            if consumer:
                return consumer
        return None

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

    def delete_consumers(self, consumers: List[models.Consumer]):
        for consumer in consumers:
            self.delete(consumer.id)

    def delete_consumer(self, consumer: models.Consumer):
        self.delete(consumer.id)

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

    def get_schedule(self):
        return self.queue.get_nowait()

    def get_schedule_of_consumer(self, consumer_id):
        key = self.generate_key(self.schedule_queue.code, consumer_id)
        item = cache_agent.qpop(key)
        if item is None:
            raise python_queue.Empty
        return json.loads(item)

    def dispatch_schedule(self, schedule: dict, consumer_id=None):
        if consumer_id is None:
            self.queue.put(schedule)
        else:
            schedule['queue'] = self.schedule_queue.code
            key = self.generate_key(self.schedule_queue.code, consumer_id)
            cache_agent.qpush(key, json.dumps(schedule))


class MachineManager:

    @staticmethod
    def all() -> List[models.Machine]:
        machines = []
        macs = set()
        for manager in ConsumerManager.all_managers():
            consumers = manager.all_consumers()
            for consumer in consumers:
                machine = models.Machine(**consumer.machine)
                if machine.mac not in macs:
                    machines.append(machine)
                    macs.add(machine.mac)
        return machines


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
        manager = ConsumerManager(self.consumer.queue)
        manager.create(self.consumer)


def consume(model):
    program = ConsumerProgram(model)
    program.start_if_not_started()
    return program
