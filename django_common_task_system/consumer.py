from typing import Optional
from django_common_task_system.choices import ConsumeStatus, ContainerStatus
from django_common_task_system.models import Consumer, Machine
from docker.errors import APIError
from threading import Thread
from docker.models.containers import Container
from datetime import datetime
from django_common_task_system.program import Program, ProgramAgent, ProgramState, Key, MapKey, ListKey
import traceback
import docker


class ContainerSetting:
    def __init__(self, program_setting: dict):
        setting = program_setting.get('container', {})
        self.image = setting.get('image', 'cone387/common-task-system-client:latest')
        self.name = setting.get('name', 'common-task-system-client-%s' % datetime.now().strftime('%Y%m%d%H%M%S'))
        self.id = setting.get('id', '')
        self.ip = setting.get('ip', '')
        self.port = setting.get('port', '')
        self.status = ContainerStatus.NONE


class ConsumerState(ProgramState):
    def __init__(self, key):
        super(ConsumerState, self).__init__(key)
        self.model = None
        self.container: Optional[Container] = None


class ConsumerProgram(Program):
    state_class = ConsumerState
    state_key = MapKey('consumers')

    def __init__(self, model: Consumer, container=None):
        self.model = model
        super().__init__(container=container)

    @property
    def program_id(self) -> int:
        return self.model.consumer_id

    @property
    def is_running(self):
        return self.model.consume_status == ConsumeStatus.RUNNING and self.container is not None and \
               self.container.status == ContainerStatus.RUNNING.lower()

    @classmethod
    def load_from_container(cls, container: Container):
        kwargs = {x.split('=')[0].strip('-'): x.split('=')[1] for x in container.attrs['Args'] if '=' in x}
        consume_url = kwargs.pop('subscription-url', None)
        consumer = Consumer(
            consume_url=consume_url,
            consume_kwargs=kwargs,
            create_time=datetime.strptime(container.attrs['Created'].split('.')[0], "%Y-%m-%dT%H:%M:%S"),
        )
        consumer.program = cls(model=consumer, container=container)
        consumer.save()

    @classmethod
    def load_consumer_from_cache(cls, cache: dict):
        program = cache.pop('program')
        machine_cache = cache.pop('machine')
        if machine_cache:
            machine = Machine(**machine_cache)
        else:
            machine = Machine.objects.local
        consumer = Consumer(machine=machine, **cache)
        if program:
            container_cache = program.get('container', {})
            if container_cache:
                docker_client = docker.from_env()
                try:
                    container = docker_client.containers.get(container_cache['short_id'])
                    if container.status == ContainerStatus.RUNNING.lower():
                        consumer.consume_status = ConsumeStatus.RUNNING
                    else:
                        consumer.consume_status = ConsumeStatus.STOPPED
                except docker.errors.NotFound:
                    container = None
                consumer.program = cls(model=consumer, container=container)
        return consumer

    def _run(self):
        model = self.model
        # pull image
        docker_client = docker.from_env()
        self.model.startup_status = ConsumeStatus.PULLING
        setting = ContainerSetting(model.program_setting)
        settings_file = '/mnt/task-system-client-settings.py'
        command = f'common-task-system-client --subscription-url="{model.consume_url}" --settings="{settings_file}"'
        try:
            container = docker_client.containers.create(
                setting.image, command=command, name=setting.name,
                volumes=[f"{model.settings_file}:{settings_file}"],
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
            container = docker_client.containers.create(setting.image,
                                                        command=command,
                                                        name=setting.name, detach=True)
        container.start()
        container = docker_client.containers.get(container.short_id)
        self.container = container

    def run(self):
        model = self.model
        model.program = self
        try:
            self._run()
            model.consume_status = ConsumeStatus.RUNNING
        except Exception as _:
            model.consume_status = ConsumeStatus.FAILED
            model.startup_log = traceback.format_exc()
        model.save()

    def stop(self, destroy=False):
        if isinstance(self.container, Container):
            self.container.stop()
            # self.container.remove()
            self.model.consume_status = ConsumeStatus.STOPPED
            self.model.save()

    def read_log(self, page=0, page_size=1000):
        if self.model.consume_status == ConsumeStatus.RUNNING.value:
            log = super(ConsumerProgram, self).read_log(page=page, page_size=page_size)
        else:
            log = self.model.startup_log
        return log


class ConsumerProgramThread(ConsumerProgram, Thread):

    def __init__(self, model):
        Thread.__init__(self, daemon=True)
        super().__init__(model=model)


def consume(model):
    program = ConsumerProgram(model)
    program.start_if_not_started()
    return program

#
# class ConsumerAgent(ProgramAgent):
#
#     def __init__(self, program_class):
#         self._program_class = program_class
#         self._program: ConsumerProgramThread = program_class()
#
#     def stop(self) -> str:
#         program: ConsumerProgramThread = self._program
#         program.stop()
#         return ''
#
#
# consumer_agent = ConsumerAgent(program_class=ConsumerProgramThread)
