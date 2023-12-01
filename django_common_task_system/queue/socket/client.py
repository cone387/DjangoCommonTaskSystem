import json
from queue import Empty
from django_common_task_system.cache_service import CacheAgent


class SocketQueue:

    def __init__(self, name=None):
        self.agent = CacheAgent()
        self.name = name

    def qsize(self):
        return self.agent.llen(self.name)

    def empty(self):
        return self.qsize() == 0

    def full(self):
        return False

    def get(self, block=True, timeout=0):
        if block:
            item = self.agent.qbpop(self.name, timeout=timeout)
            return json.loads(item)
        return self.get_nowait()

    def get_nowait(self):
        item = self.agent.qpop(self.name)
        if item is None:
            raise Empty
        return json.loads(item)

    def put(self, item: dict):
        item = json.dumps(item)
        self.agent.qpush(self.name, item)
