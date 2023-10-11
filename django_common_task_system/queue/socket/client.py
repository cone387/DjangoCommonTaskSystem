import json
import socket
from queue import Empty
from django_common_task_system.cache_service import CacheAgent


class SocketQueue:

    def __init__(self, name=None):
        self.agent = CacheAgent()
        self.name = name or 'default'

    def qsize(self):
        return self.agent.llen(self.name)

    def empty(self):
        return self.qsize() == 0

    def full(self):
        return False

    def get(self, block=True, timeout=0):
        if block:
            return self.agent.bpop(self.name, timeout=timeout)
        return self.get_nowait()

    def get_nowait(self):
        item = self.agent.pop(self.name)
        if item is None:
            raise Empty
        return json.loads(item)

    def put(self, item: dict):
        item = json.dumps(item)
        self.agent.push(self.name, item)


# class SocketQueue:
#     def __init__(self, name=None, host='127.0.0.1', port=55555):
#         self.name = name or 'default'
#         self.host = host
#         self.port = port
#         self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#         # self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
#         self._socket.connect((self.host, self.port))
#         # self._socket.settimeout(1)
#         # self._socket.setblocking(False)
#         # self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
#
#     # def connect(self):
#     #     self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#     #     self._socket.connect((self.host, self.port))
#     #     self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
#
#     def close(self):
#         self._socket.close()
#
#     def execute(self, command, *args, **kwargs):
#         _socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#         _socket.connect((self.host, self.port))
#         commands = [command, f'qname={self.name}', *[f"{k}={v}" for k, v in kwargs.items()], *[f'${x}' for x in args]]
#         _socket.send((f'\r\n'.join(commands) + '\r\n\r\n').encode())
#         data = _socket.recv(4096)
#         while not data.endswith(b'\r\n\r\n'):
#             data += _socket.recv(4096)
#         _socket.close()
#         data = data.strip(b'\r\n').decode()
#         if data.startswith('-'):
#             raise Exception(data[1:])
#         return data
#
#     def __enter__(self):
#         return self
#
#     def __exit__(self, exc_type, exc_val, exc_tb):
#         self.close()
#
#     def __repr__(self):
#         return f'<{type(self).__name__} {self.host}:{self.port}>'
#
#     def __str__(self):
#         return f'<{type(self).__name__} {self.host}:{self.port}>'
#
#     @staticmethod
#     def _load_item(item):
#         return json.loads(item[1:])
#
#     def get(self, block=True, timeout=0):
#         if block:
#             return self._load_item(self.execute('bpop', timeout=timeout))
#         return self.get_nowait()
#
#     def get_nowait(self):
#         ret = self.execute('pop')
#         if ret == '*-1':
#             raise Empty
#         return self._load_item(ret)
#
#     def put(self, item: dict):
#         item = json.dumps(item)
#         self.execute('push', item)
#
#     def qsize(self):
#         return int(self.execute('llen')[1:])
#
#     def empty(self):
#         return self.qsize() == 0
#
#     def full(self):
#         return False
#
#     # @classmethod
#     # def validate(cls, **kwargs):
#     #     _socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#     #     _socket.connect(('127.0.0.1', 55555))


if __name__ == '__main__':
    import time
    queue = SocketQueue()
    while True:
        queue.put({"time": str(time.time())})
        o = queue.get()
        print(o)
        time.sleep(0.1)
