from multiprocessing import Process, set_start_method


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

    def terminate(self, pid):
        if pid in self._processes:
            self._processes[pid].terminate()
        else:
            raise ValueError('pid %s not found' % pid)

    def terminate_all(self):
        for process in self._processes.values():
            process.terminate()


ProcessManager = _ProcessManager()
