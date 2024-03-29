import asyncio
import re
import pickle
import json
import inspect
from asyncio import StreamReader, StreamWriter
from datetime import datetime
from typing import Union, Dict, Callable, Coroutine, Optional
from urllib.parse import urlparse


class BaseResponse:

    def __init__(self, text: str = None, status=200):
        self.text = text
        self.status = status

    def __bytes__(self):
        return self.text.encode()

    def __str__(self):
        return str(self.text)


class Response(BaseResponse):
    def __init__(self, text: str = None, status=200):
        if isinstance(text, (dict, list, tuple)):
            text = json.dumps(text)
        if text is None:
            text = '*-1'
        elif status == 200:
            text = f"+{text}"
        else:
            text = f"-{text}"
        super(Response, self).__init__(text, status)

    def __bytes__(self):
        return self.text.encode() + b'\r\n\r\n'


NullResponse = Response('\r\n\r\n')


class HttpResponse(BaseResponse):

    def __init__(self, text, status=200, content_type='application/json'):
        if text is None:
            text = {"error": "no content"}
        if status != 200:
            if isinstance(text, str):
                text = {"error": text}
        if isinstance(text, (dict, list, tuple)):
            text = json.dumps(text)
        self.content_type = content_type
        super(HttpResponse, self).__init__(text, status)

    def __bytes__(self):
        return (
            f"HTTP/1.1 {self.status}\r\n"
            f"Content-type: {self.content_type}\r\n"
            f"\r\n"
            f"{self.text}"
        ).encode()


HTTPNullResponse = HttpResponse('')


class Queue:
    def __init__(self, queue: asyncio.Queue, name):
        self.name = name
        self.queue = queue
        self.create_time = datetime.now()

    # def keys(self):
    #     """
    #         当对实例化对象使用dict(obj)的时候, 会调用这个方法,这里定义了字典的键, 其对应的值将以obj['name']的形式取,
    #         但是对象是不可以以这种方式取值的, 为了支持这种取值, 可以为类增加一个方法
    #     """
    #     return 'name', 'queue', 'create_time'
    #
    # def __getitem__(self, item):
    #     return getattr(self, item)


"""
协议格式
COMMAND Optional[QUEUE_NAME] QUEUE/1.0\r\n
ARGS\r\n
\r\n\r\n

"""

"""
command
list
lpop
blpop
rpop
brpop
lpush
rpush
LINDEX key index
"""


_queue_header_pattern = re.compile(r'(?P<command>\w+) ((?P<queue_name>[\w:/\.]+) )?QUEUE/1.0\r\n')
_http_header_pattern = re.compile(r'(?P<command>\w+) (?P<url>\S+) HTTP/1.1\r\n')
_queue_mapping: Dict[str, Queue] = {}

Command = Callable[[Optional[str], Optional[asyncio.Queue], ...], Union[Response, HttpResponse, Coroutine]]


def get_or_create_queue(name) -> asyncio.Queue:
    queue = _queue_mapping.get(name)
    if queue is None:
        queue = Queue(asyncio.Queue(), name)
        _queue_mapping[name] = queue
    return queue.queue


def list_queues(queue_name: Optional[str], queue: Optional[asyncio.Queue]):
    return [{
        'name': x.name,
        'create_time': x.create_time.strftime('%Y-%m-%d %H:%M:%S'),
        'size': x.queue.qsize()
    } for x in _queue_mapping.values()]


def pop_queue(queue_name, queue: Optional[asyncio.Queue]):
    if queue is None:
        return None
    try:
        return queue.get_nowait()
    except asyncio.QueueEmpty:
        return None


async def bpop_queue(queue_name, queue: Optional[asyncio.Queue], timeout: int = 0):
    queue = get_or_create_queue(queue_name)
    if timeout <= 0:
        return await queue.get()
    try:
        return await asyncio.wait_for(queue.get(), timeout=timeout)
    except asyncio.TimeoutError:
        return None


def push_queue(queue_name, queue: Optional[asyncio.Queue], *values):
    if not values:
        raise Exception("message is empty")
    queue = get_or_create_queue(queue_name)
    for value in values:
        queue.put_nowait(value)
    return len(values)


def delete_queue(queue_name, queue: Optional[asyncio.Queue]):
    if queue is None:
        return 0
    del _queue_mapping[queue_name]
    return 1


def llen(queue_name, queue: Optional[asyncio.Queue]):
    if queue is None:
        return 0
    return queue.qsize()


_available_commands = {
    'list': list_queues,
    'pop': pop_queue,
    'bpop': bpop_queue,
    'push': push_queue,
    'delete': delete_queue,
    'llen': llen,
    # 'LINDEX': lambda: HttpResponse(''),
}


async def handle_http_request(header, message) -> BaseResponse:
    """
    :param header: GET /hello.txt HTTP/1.1
    :param message:
    :return:
    """
    result = _http_header_pattern.search(header)
    if result is None:
        raise Exception("invalid http header")
    method, url = result.groups()
    if method != 'GET':
        raise Exception("invalid http method %s" % method)
    url_result = urlparse(url)
    command_name = url_result.path.strip('/')
    command: Command = _available_commands.get(command_name)
    if command is None:
        raise Exception("invalid command name %s" % command_name)
    split_params = str(url_result.query).split('&') if url_result.query else []
    params = {x.split('=')[0]: x.split('=')[1] for x in split_params}
    queue_name = params.pop('queue', None)
    queue = getattr(_queue_mapping.get(queue_name), 'queue', None)
    spec = inspect.getfullargspec(command)
    # 检查是否缺少参数
    # TODO: 检查是否缺少必须的参数
    # 检查参数类型是否正确
    for k, v in params.items():
        if k not in spec.args and k != spec.varargs:
            raise Exception("invalid param %s" % k)
        annotation = spec.annotations.get(k)
        if annotation is not None:
            try:
                params[k] = annotation(v)
            except Exception as e:
                raise Exception("invalid param %s, expect %s" % (k, spec.annotations[k]))
    ret = command(queue_name, queue, *params.values())
    if isinstance(ret, BaseResponse):
        return ret
    elif isinstance(ret, Coroutine):
        ret = await ret
    return HttpResponse(ret)


async def handle_queue_request(header, message: bytes) -> BaseResponse:
    result = _queue_header_pattern.search(header)
    if result is None:
        raise Exception("invalid queue header")
    command_name, _, queue_name = result.groups()
    command: Command = _available_commands.get(command_name)
    if command is None:
        raise Exception("invalid command name %s" % command_name)
    queue = getattr(_queue_mapping.get(queue_name), 'queue', None)
    line_args = message.strip(b'\r\n\r\n').decode()
    spec = inspect.getfullargspec(command)
    # check queue and queue_name
    annotation = spec.annotations.get('queue_name')
    if queue_name is None and not (annotation is not None and annotation._name == 'Optional'):
        raise Exception("queue_name is required")
    annotation = spec.annotations.get('queue')
    if queue is None and not (annotation is not None and annotation._name == 'Optional'):
        raise Exception("queue %s not found" % queue_name)
    args = []
    if line_args:
        line_args = line_args.split('\r\n')
        spec = inspect.getfullargspec(command)
        if spec.varargs is None and len(line_args) != len(spec.args) - 2:
            raise Exception("invalid args length")
        elif spec.varargs:
            args = line_args[len(spec.args) - 2:]
        for k, v in zip(spec.args[2:], line_args):
            annotation = spec.annotations.get(k)
            if annotation is not None:
                try:
                    args.append(annotation(v))
                except Exception as e:
                    raise Exception("invalid param %s, expect %s" % (k, spec.annotations[k]))
    ret = command(queue_name, queue, *args)
    if isinstance(ret, BaseResponse):
        return ret
    elif isinstance(ret, Coroutine):
        ret = await ret
    return Response(ret)


async def handle_client(reader: StreamReader, writer: StreamWriter):
    """
    模拟Redis协议
    简单字符串以+开头，后面跟着字符串，例如 +OK
    错误消息以-开头，后面跟着错误消息，例如 -ERR unknown command 'foobar'
    """
    print("connect from ", writer.get_extra_info('peername'))
    try:
        header = await asyncio.wait_for(reader.readline(), timeout=5)
    except asyncio.TimeoutError:
        response = Response("read timeout on server", status=408)
    except Exception as e:
        response = Response(str(e), status=500)
    else:
        header = header.decode()
        if 'HTTP' in header:
            request_handler = handle_http_request
            ResponseClass = HttpResponse
        else:
            request_handler = handle_queue_request
            ResponseClass = Response
        try:
            message = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), timeout=5)
            response = await request_handler(header, message)
        except asyncio.TimeoutError:
            response = ResponseClass("read timeout on server", status=408)
        except Exception as e:
            response = ResponseClass(str(e), status=500)
    try:
        writer.write(bytes(response))
        await writer.drain()
    except Exception as e:
        print(e)
    finally:
        writer.close()
        # if response.status != 200 or isinstance(response, HttpResponse):
        #     writer.close()


async def main():
    import socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    server_socket.bind(('127.0.0.1', 55555))
    server = await asyncio.start_server(handle_client, sock=server_socket)
    addr = server_socket.getsockname()
    print(f'Serving on {addr}')

    async with server:
        await server.serve_forever()


def start_queue_server():
    asyncio.run(main())


def ensure_server_running():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', 55555))
        s.close()
    except ConnectionRefusedError:
        from multiprocessing import Process
        p = Process(target=start_queue_server, daemon=True)
        p.start()


if __name__ == '__main__':
    start_queue_server()
