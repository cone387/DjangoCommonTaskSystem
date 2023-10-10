import asyncio

#
# async def send_message(message):
#     reader, writer = await asyncio.open_connection('127.0.0.1', 8888)
#     print(f'Send: {message}')
#     writer.write(message.encode())
#     await writer.drain()
#     try:
#         text = await asyncio.wait_for(reader.read(), timeout=30)
#         print("Received:", text.decode())
#     except asyncio.TimeoutError:
#         print('client timeout ')
#
#     writer.close()
#
#
# asyncio.run(send_message('Hello World!\r\n\r\n'))

import socket

def send_message(message):
    # 创建一个 socket 对象
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # 连接到服务器
    client_socket.connect(('127.0.0.1', 8888))

    print(f'Send: {message}')
    client_socket.send(message.encode())

    # 接收服务器的响应
    response = client_socket.recv(4096)
    print("Received:", response)

    # 关闭连接
    client_socket.close()

# 发送消息
# send_message('Hello World!\r\n\r\n')


class SocketQueue:
    def __init__(self, name=None, host='127.0.0.1', port=8888):
        self.name = name or 'default'
        self.host = host
        self.port = port
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self._socket.connect((self.host, self.port))
        # self._socket.settimeout(1)
        # self._socket.setblocking(False)
        # self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

    # def connect(self):
    #     self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #     self._socket.connect((self.host, self.port))
    #     self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

    def close(self):
        self._socket.close()

    def execute(self, command, *args):
        _socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _socket.connect((self.host, self.port))
        _socket.send((f'{command} {self.name} QUEUE/1.0\r\n' + '\r\n'.join(args) + '\r\n\r\n').encode())
        data = _socket.recv(4096)
        while not data.endswith(b'\r\n\r\n'):
            data += _socket.recv(4096)
        _socket.close()
        data = data.strip(b'\r\n').decode()
        if data.startswith('-'):
            raise Exception(data[1:])
        return data[1:]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __repr__(self):
        return f'<{type(self).__name__} {self.host}:{self.port}>'

    def __str__(self):
        return f'<{type(self).__name__} {self.host}:{self.port}>'

    def get(self, block=True, timeout=0):
        if block:
            return self.execute('bpop', str(timeout))
        return self.get_nowait()

    def get_nowait(self):
        return self.execute('pop')

    def put(self, item: str):
        self.execute('push', item)

    def qsize(self):
        return self.execute('llen')

    def empty(self):
        return self.qsize() == 0

    def full(self):
        return False

    def validate(self):
        return self.execute('ping QUEUE/1.0\r\n')


if __name__ == '__main__':
    import time
    queue = SocketQueue()
    while True:
        queue.put(str(time.time()))
        o = queue.get()
        print(o)
        time.sleep(0.1)
