from django_common_task_system.choices import TaskClientStatus
from django_common_task_system.models import Consumer, DockerEngine
from docker.errors import APIError
from threading import Thread
from docker.models.containers import Container
from django_common_task_system.program import Program, ProgramAgent, ProgramState
import traceback
import docker


class ConsumerState(ProgramState):
    def __init__(self, key):
        super(ConsumerState, self).__init__(key)
        self.image = ''
        self.container_name = ''
        self.container_id = ''
        self.container_ip = ''
        self.container_port = ''
        self.startup_status = TaskClientStatus.INIT


def start_in_container(model: Consumer):
    # pull image
    docker_client = docker.from_env()
    model.startup_status = TaskClientStatus.PULLING
    engine: DockerEngine = model.engine
    settings_file = '/mnt/task-system-client-settings.py'
    command = f'common-task-system-client --subscription-url="{model.subscription_url}" --settings="{settings_file}"'
    try:
        container = docker_client.containers.create(
            engine.image, command=command, name=engine.container_name,
            volumes=[f"{model.settings_file}:{settings_file}"],
            detach=True
        )
    except docker.errors.ImageNotFound:
        image, tag = engine.image.split(':') if ':' in engine.image else (
            engine.image, None)
        for _ in range(3):
            try:
                docker_client.images.pull(image, tag=tag)
                break
            except APIError:
                pass
        else:
            raise RuntimeError('pull image failed: %s' % engine.image)
        container = docker_client.containers.create(engine.image,
                                                    command=command,
                                                    name=engine.container_name, detach=True)
    container.start()
    container = docker_client.containers.get(container.short_id)
    return container


class ConsumerProgram(Program):
    state_key = 'client'
    state_class = ConsumerState

    def __init__(self, model):
        self.model = model
        super().__init__(name='client')

    def run(self):
        model = self.model
        settings = model.program_settings
        try:
            container = start_in_container(model)
            model.startup_status = TaskClientStatus.RUNNING
            self.state.commit_and_push(
                ident=container.short_id,
                name=container.name,
                container_status=container.status,
                **settings,
            )
        except Exception:
            model.startup_status = TaskClientStatus.FAILED
            model.startup_log = traceback.format_exc()
            self.state.commit_and_push(
                startup_status=model.startup_status,
                startup_log=model.startup_log,
                **settings,
            )


class ConsumerProgramThread(ConsumerProgram, Thread):

    def __init__(self, model):
        Thread.__init__(self, daemon=True)
        super().__init__(model)

    def run(self):
        model = self.model
        # pull image
        docker_client = docker.from_env()
        self.model.startup_status = TaskClientStatus.PULLING
        engine: DockerEngine = model.engine
        settings_file = '/mnt/task-system-client-settings.py'
        command = f'common-task-system-client --subscription-url="{model.subscription_url}" --settings="{settings_file}"'
        try:
            container = docker_client.containers.create(
                engine.image, command=command, name=engine.container_name,
                volumes=[f"{model.settings_file}:{settings_file}"],
                detach=True
            )
        except docker.errors.ImageNotFound:
            image, tag = engine.image.split(':') if ':' in engine.image else (
                engine.image, None)
            for _ in range(3):
                try:
                    docker_client.images.pull(image, tag=tag)
                    break
                except APIError:
                    pass
            else:
                raise RuntimeError('pull image failed: %s' % engine.image)
            container = docker_client.containers.create(engine.image,
                                                        command=command,
                                                        name=engine.container_name, detach=True)
        container.start()
        container = docker_client.containers.get(container.short_id)
        return container

    def stop(self):
        program: Container = self.model.program
        if isinstance(program):
            program.stop()
            program.remove()


class ClientRunner:

    def read_log(self, page=1, page_size=10):
        if isinstance(self.runner, Container):
            return self.runner.logs(tail=1000)


def consume(model):
    program = ConsumerProgramThread(model)
    program.start()
    return program


class ConsumerAgent(ProgramAgent):

    def __init__(self, program_class):
        self._program_class = program_class
        self._program: ConsumerProgramThread = program_class()

    def stop(self) -> str:
        program: ConsumerProgramThread = self._program
        program.stop()
        return ''


consumer_agent = ConsumerAgent(program_class=ConsumerProgramThread)
