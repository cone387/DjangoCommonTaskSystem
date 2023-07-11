from .base import BaseExecutor, NoRetryException
from django_common_task_system.system_task.builtins import builtins
import os
import zipfile
import shutil
import subprocess
import sys

SYS_ENCODING = sys.getdefaultencoding()


TMP_DIR = os.path.join(os.getcwd(), 'tmp')
if not os.path.exists(TMP_DIR):
    os.makedirs(TMP_DIR)


def run_in_subprocess(cmd):
    logs = []
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if out:
        logs.append(out.decode(SYS_ENCODING))
    if err:
        logs.append(err.decode(SYS_ENCODING))
    return not err, logs


class ProgramExecutor:

    def __new__(cls, path, file, args=None):
        if cls is ProgramExecutor:
            if not file:
                raise Exception('file is required')
            elif file.endswith('.py'):
                return PythonExecutor(file, args)
            elif file.endswith('.zip'):
                return ZipExecutor(file, args)
            elif file.endswith('.sh'):
                return ShellExecutor(file, args)
            raise Exception('Unsupported file type %s' % file)
        else:
            return super().__new__(cls)

    def __init__(self, path, file, args=None):
        self.working_path = path
        self.file = file
        if args:
            self.args = [x.strip() for x in args.split(' ')]
        else:
            self.args = []
        self.logs = []

    def prepare(self):
        pass

    def assert_runnable(self):
        pass

    def run(self):
        succeed, self.logs = run_in_subprocess(self.entrypoint)
        if not succeed:
            raise NoRetryException('Failed to run %s, %s' % (self.file, '\n'.join(self.logs)))

    @property
    def entrypoint(self):
        raise NotImplementedError


class Docker:

    def __init__(self, program: ProgramExecutor, image):
        self.program = program
        self.image = image
        self.working_path = '/home/admin/task-system-client'
        self.logs = []

    def build_image(self):
        cmd = 'docker pull %s' % self.image
        succeed, logs = run_in_subprocess(cmd)
        if not succeed:
            raise NoRetryException('Failed to build docker image %s, %s' % (self.image, '\n'.join(logs)))
        self.logs = logs

    def start_container(self):
        cmd = 'docker run --rm -v %s:%s %s %s' % (
            self.program.working_path, self.working_path, self.image,
            self.program.entrypoint.replace(self.program.working_path, self.working_path).replace(os.sep, '/'))
        succeed, logs = run_in_subprocess(cmd)
        if not succeed:
            raise NoRetryException('Failed to start docker container %s, %s' % (self.image, '\n'.join(logs)))
        self.logs = logs

    def run(self):
        self.build_image()
        self.start_container()


class PythonExecutor(ProgramExecutor):

    @property
    def entrypoint(self):
        return ' '.join(['python', self.file] + self.args)


class ZipExecutor(ProgramExecutor):

    def __init__(self, path, file, args=None):
        super().__init__(path, file, args)
        self.program = None

    def prepare(self):
        zip_file = zipfile.ZipFile(self.file)
        zip_file.extractall(self.working_path)
        zip_file.close()

        shell = os.path.join(self.working_path, 'main.sh')
        python = os.path.join(self.working_path, 'main.py')
        if os.path.exists(shell):
            self.program = ShellExecutor(self.working_path, shell, self.args)
        elif os.path.exists(python):
            self.program = PythonExecutor(self.working_path, python, self.args)

    def assert_runnable(self):
        if not self.program:
            raise NoRetryException('main.py or main.sh not found')

    @property
    def entrypoint(self):
        return self.program.entrypoint

    def run(self):
        self.program.assert_runnable()
        self.program.run()


class ShellExecutor(ProgramExecutor):

    def assert_runnable(self):
        if sys.platform == 'win32':
            raise NoRetryException('shell is not supported in windows')

    @property
    def entrypoint(self):
        return ' '.join(['sh', self.file] + self.args)


class CustomProgramExecutor(BaseExecutor):
    name = builtins.tasks.custom_program_parent_task.name

    def execute(self):
        custom_program = self.schedule.task.config.get('custom_program')
        file = custom_program.get('executable')
        args = custom_program.get('args')
        container_image = custom_program.get('docker_image') or 'cone387/common-task-system-client'
        run_in_container = custom_program.get('run_in_docker', False)
        if not os.path.exists(file):
            raise NoRetryException('File(%s) not found' % file)
        # prepare program working path
        working_path = os.path.join(TMP_DIR, str(self.schedule.task.id))
        if not os.path.exists(working_path):
            os.mkdir(working_path)
        try:
            # prepare program files
            program_file = shutil.copy(file, os.path.join(working_path, os.path.basename(file)))
            program = ProgramExecutor(working_path, file=program_file, args=args)
            program.prepare()
            if run_in_container:
                docker = Docker(program, image=container_image)
                docker.run()
                logs = docker.logs
            else:
                program.assert_runnable()
                logs = program.run()
            # clean up
        finally:
            shutil.rmtree(working_path)
        return logs
