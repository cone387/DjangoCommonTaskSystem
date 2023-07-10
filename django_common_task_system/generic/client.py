from multiprocessing import Process, set_start_method
from django_common_task_system.generic.models import TaskClient
import os
import subprocess
import json
import sys

from django_common_task_system.utils.algorithm import get_md5

SYS_ENCODING = sys.getdefaultencoding()


def run_in_subprocess(cmd):
    logs = []
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if out:
        logs.append(out.decode(SYS_ENCODING))
    if err:
        logs.append(err.decode(SYS_ENCODING))
    return not err, logs


class ClientManager:

    @classmethod
    def start_in_process(cls, client: TaskClient):
        set_start_method('spawn', True)
        try:
            from task_system_client.main import start_task_system
        except ImportError:
            os.system('pip install common-task-system-client')
            try:
                from task_system_client.main import start_task_system
            except ImportError:
                raise ImportError('common-task-system-client install failed')
        os.environ['COMMON_TASK_SYSTEM_MODULE'] = client.settings_file
        p = Process(target=start_task_system, daemon=True)
        p.start()
        client.process_id = p.pid
        client.status = p.is_alive()

    @classmethod
    def start_in_docker(cls, process: TaskClient):
        # pull image
        image = process.docker_image
        if not image:
            raise ValueError('docker image is required')
        err, logs = run_in_subprocess(f'docker pull {image}')
        if err:
            raise RuntimeError('pull docker image failed: %s' % image)
        # run container
        name = 'system-process-default'
        log_file = os.path.join(os.getcwd(), 'logs', f'{name}.log')
        cmd = f'docker run -d --name {name} -v {log_file}:/logs/{name}.log {image}'
        err, logs = run_in_subprocess(cmd)
        if err:
            raise RuntimeError('run docker container failed: %s' % image)
        # get container id
        cmd = f'docker ps -a | grep {name} | awk \'{{print $1}}\''
        err, logs = run_in_subprocess(cmd)
        if err:
            raise RuntimeError('get docker container id failed: %s' % image)

    @classmethod
    def start_client(cls, client: TaskClient):
        if client.run_in_docker:
            cls.start_in_docker(client)
        else:
            cls.start_in_process(client)

    def stop(self, process: TaskClient):
        pass

    def stop_all(self):
        pass
