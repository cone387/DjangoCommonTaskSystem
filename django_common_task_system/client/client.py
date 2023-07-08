from multiprocessing import Process, set_start_method
from django_common_task_system.system_task.forms import get_md5
from django_common_task_system.system_task.models import SystemProcess
import os
import subprocess
import json
import sys


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


class ProcessManager:
    all = []

    @classmethod
    def start_in_process(cls, process: SystemProcess):
        logs_path = os.path.join(os.getcwd(), 'logs')
        if not os.path.exists(logs_path):
            os.mkdir(logs_path)
        name = get_md5("%s%s%s%s%s" % (
            process.process_id, process.process_name,
            process.docker_image, process.docker_id, process.docker_name
        ))
        process.log_file = os.path.join(logs_path, f'{name}.log')

        set_start_method('spawn', True)
        try:
            from task_system_client.main import start_task_system
        except ImportError:
            os.system('pip install task_system_client')
            try:
                from task_system_client.main import start_task_system
            except ImportError:
                raise ImportError('task_system_client install failed')
        with open(process.log_file, 'w') as f:
            json.dump(process.settings, f)
        os.environ['COMMON_TASK_SYSTEM_MODULE'] = ''
        p = Process(target=start_task_system, daemon=True)
        p.start()
        process.process_id = p.pid
        cls.all.append(process)

    @classmethod
    def start_in_docker(cls, process: SystemProcess):
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
    def start_process(cls, process: SystemProcess):
        if process.run_on_docker:
            cls.start_in_docker(process)
        else:
            cls.start_in_process(process)

    def stop(self, process: SystemProcess):
        if pid in self._processes:
            self._processes[pid].kill()
            self._processes.pop(pid)

    def stop_all(self):
        pass
