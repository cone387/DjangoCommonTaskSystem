from multiprocessing import Process, set_start_method
import os


class _ProcessManager:

    def __init__(self):
        self._processes = {}

    @property
    def all(self):
        return [x for x in self._processes.values() if x.is_alive()]

    @property
    def all_process_ids(self):
        return [k for k, v in self._processes.items() if v.is_alive()]

    def create(self, target, *args, **kwargs) -> Process:
        set_start_method('spawn', True)
        process = Process(target=target, args=args, kwargs=kwargs, daemon=True)
        process.start()
        self._processes[process.pid] = process
        return process

    def kill(self, pid):
        if pid in self._processes:
            self._processes[pid].kill()
            self._processes.pop(pid)

    def kill_all(self):
        for process in self._processes.values():
            process.kill()
        self._processes.clear()

    def terminate(self, pid):
        if pid in self._processes:
            self._processes[pid].terminate()
        else:
            raise ValueError('pid %s not found' % pid)

    def terminate_all(self):
        for process in self._processes.values():
            process.terminate()


ProcessManager = _ProcessManager()


def start_in_process(queue_url):
    logs_path = os.path.join(os.getcwd(), 'logs')
    if not os.path.exists(logs_path):
        os.mkdir(logs_path)
    SystemProcess.objects.all().delete()
    name = 'system-process-default'
    log_file = os.path.join(logs_path, f'{name}.log')
    instance = SystemProcess(
        process_name=name,
        log_file=log_file
    )
    process = ProcessManager.create(start_system_client, instance.log_file)
    instance.process_id = process.pid
    instance.save()


def start_in_docker(queue_url):
    pass


def start_client(queue_url, run_in_docker=False):
    if run_in_docker:
        # check docker is enabled
        if os.system('docker ps') != 0:
            raise RuntimeError('docker is not enabled')
        start_in_docker()
    try:
        from task_system_client.main import start_task_system
    except ImportError:
        os.system('pip install task_system_client')
        from task_system_client.main import start_task_system

    start_in_process(queue_url)

