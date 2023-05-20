from .base import BaseExecutor, NoRetryException
from django_common_task_system.system_task.builtins import builtins
import os
import zipfile
import shutil
import subprocess
import sys


TMP_DIR = os.path.join(os.getcwd(), 'tmp')
if not os.path.exists(TMP_DIR):
    os.makedirs(TMP_DIR)


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

    def prepare(self):
        pass

    def assert_runnable(self):
        pass

    def run(self):
        pass


class PythonExecutor(ProgramExecutor):

    def run(self):
        subprocess.call(['python', self.file] + self.args)


class ZipExecutor(ProgramExecutor):

    def prepare(self):
        zip_file = zipfile.ZipFile(self.file)
        zip_file.extractall(self.working_path)
        zip_file.close()

    def assert_runnable(self):
        if not (os.path.exists(os.path.join(self.working_path, 'main.py'))
                or os.path.exists(os.path.join(self.working_path, 'main.sh'))):
            raise NoRetryException('main.py or main.sh not found')

    def run(self):
        shell = os.path.join(self.working_path, 'main.sh')
        python = os.path.join(self.working_path, 'main.py')
        if os.path.exists(shell):
            program = ShellExecutor(self.working_path, shell, self.args)
        else:
            program = PythonExecutor(self.working_path, python, self.args)
        program.assert_runnable()
        program.run()


class ShellExecutor(ProgramExecutor):

    def assert_runnable(self):
        if sys.platform == 'win32':
            raise NoRetryException('shell is not supported in windows')

    def run(self):
        subprocess.call(['sh', self.file] + self.args)


class CustomProgramExecutor(BaseExecutor):
    name = builtins.tasks.custom_program_parent_task.name

    def execute(self):
        file = self.schedule.task.config.get('executable_file')
        args = self.schedule.task.config.get('executable_args')
        if not os.path.exists(file):
            raise NoRetryException('File(%s) not found' % file)
        # prepare program working path
        working_path = os.path.join(TMP_DIR, str(self.schedule.task.id))
        if not os.path.exists(working_path):
            os.mkdir(working_path)
        # prepare program files
        program_file = shutil.copy(file, os.path.join(working_path, os.path.basename(file)))
        program = ProgramExecutor(working_path, file=program_file, args=args)
        program.prepare()
        program.assert_runnable()
        program.run()
        # clean up
        shutil.rmtree(working_path)
