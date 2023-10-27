import asyncio
import re
import json
import inspect
import os
import socket
import importlib
import time
from asyncio import StreamReader, StreamWriter
from datetime import datetime
from typing import Union, Dict, Callable, Coroutine, Optional, List


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
COMMAND\r\n
ARGS\r\n
\r\n\r\n

"""


class TTLString(str):
    """
    为字符串增加过期时间
    """

    def __new__(cls, value, expire=0):
        obj = super(TTLString, cls).__new__(cls, value)
        obj.expire = expire
        obj.create_time = time.time()
        return obj

    @property
    def expired(self):
        if self.expire <= 0:
            return False
        return time.time() - self.create_time > self.expire


_queue_header_pattern = re.compile(r'(?P<command>\w+) ((?P<queue_name>[\w:/\.]+) )?QUEUE/1.0\r\n')
_http_header_pattern = re.compile(r'(?P<command>\w+) (?P<url>\S+) HTTP/1.1\r\n')
_http_path_pattern = re.compile(r'/(?P<path>\w+)?\??(?P<query>.*)')
_queue_mapping: Dict[str, Queue] = {}
_cache_mapping: Dict[str, Union[TTLString, Dict, List]] = {}


Command = Callable[[Optional[str], Optional[asyncio.Queue], ...], Union[Response, HttpResponse, Coroutine]]


def get_or_create_queue(qname) -> asyncio.Queue:
    queue = _queue_mapping.get(qname)
    if queue is None:
        queue = Queue(asyncio.Queue(), qname)
        _queue_mapping[qname] = queue
    return queue.queue


def get_queue(qname) -> Union[asyncio.Queue, None]:
    queue = _queue_mapping.get(qname)
    if queue is None:
        return None
    return queue.queue


def _list():
    cache = {
        k: {
            'value': v,
            'expire': v.expire,
            'create_time': datetime.fromtimestamp(v.create_time).strftime('%Y-%m-%d %H:%M:%S')
        }
        if isinstance(v, TTLString) else v
        for k, v in _cache_mapping.items()
    }
    return {
        'queues': [{
            'name': x.name,
            'create_time': x.create_time.strftime('%Y-%m-%d %H:%M:%S'),
            'size': x.queue.qsize()
        } for x in _queue_mapping.values()],
        **cache
    }


def _qpop(qname):
    queue = get_queue(qname)
    if queue is None:
        return None
    try:
        return queue.get_nowait()
    except asyncio.QueueEmpty:
        return None


async def _qbpop(qname, timeout: int = 0):
    queue = get_or_create_queue(qname)
    if timeout <= 0:
        return await queue.get()
    try:
        return await asyncio.wait_for(queue.get(), timeout=timeout)
    except asyncio.TimeoutError:
        return None


def _qpush(*values, qname=None):
    if not values:
        raise Exception("message is empty")
    queue = get_or_create_queue(qname)
    for value in values:
        queue.put_nowait(value)
    return len(values)


def _pop(name):
    clist = _cache_mapping.get(name)
    if not clist:
        return None
    if isinstance(clist, list):
        try:
            return clist.pop(0)
        except IndexError:
            return None
    else:
        raise Exception("key %s is not a list, the type is %s" % (name, type(clist)))


async def _bpop(name, timeout: int = 0):
    clist = _cache_mapping.get(name)
    if not clist:
        return None
    while not clist:
        await asyncio.sleep(0.1)
        clist = _cache_mapping.get(name)
    if isinstance(clist, list):
        return clist.pop(0)
    else:
        raise Exception("key %s is not a list, the type is %s" % (name, type(clist)))


def _push(*values, name=None):
    if not values:
        raise Exception("message is empty")
    clist = _cache_mapping.setdefault(name, [])
    for value in values:
        clist.append(value)
    return len(values)


def _delete(qname):
    if qname in _queue_mapping:
        del _queue_mapping[qname]
        return 1
    return 0


def _llen(qname):
    queue = get_queue(qname)
    if queue is None:
        return 0
    return queue.qsize()


def _set(key: str, value: str, expire: int = 0):
    _cache_mapping[key] = TTLString(value, expire=expire)
    return 1


def _get(key: str):
    return _cache_mapping.get(key)


def _mset(data: str, expire: int = 0):
    mapping = json.loads(data)
    for k, v in mapping.items():
        # if '=' not in arg:
        #     raise Exception("invalid param %s, expect key=value" % arg)
        # k, v = arg.split('=', 1)
        _cache_mapping[k] = TTLString(v, expire=expire)
    return len(mapping)


def _hset(name, data: str):
    mapping = json.loads(data)
    hmap = _cache_mapping.setdefault(name, dict())
    hmap.update(mapping)
    return len(mapping)


def _hget(name, key):
    hmap = _cache_mapping.get(name)
    if hmap is None:
        return None
    if not isinstance(hmap, dict):
        raise Exception("key %s is not a map, use get instead" % name)
    return hmap.get(key)


def _hgetall(name: str) -> Union[Dict, None]:
    item = _cache_mapping.get(name)
    if item is None:
        return None
    if not isinstance(item, dict):
        raise Exception("key %s is not a map, use get instead" % name)
    return item


def _hdel(name, key):
    hmap = _cache_mapping.get(name)
    if hmap is None:
        return None
    if not isinstance(hmap, dict):
        raise Exception("key %s is not a map, use get instead" % name)
    return hmap.pop(key, None)


_available_commands = {
    'list': _list,
    'pop': _pop,
    'bpop': _bpop,
    'push': _push,
    'qpop': _qpop,
    'qbpop': _qbpop,
    'qpush': _qpush,
    'delete': _delete,
    'llen': _llen,
    'set': _set,
    'get': _get,
    'mset': _mset,
    'hset': _hset,
    'hget': _hget,
    'hgetall': _hgetall,
    'hdel': _hdel,
    # 'LINDEX': lambda: HttpResponse(''),
}


def parse_command_args(command: Command, params_str: str, sep='&') -> (List[str], Dict[str, str]):
    split_params = params_str.split(sep) if params_str else []
    spec = inspect.getfullargspec(command)
    args = []
    kwargs = {}
    for param_str in split_params:
        if param_str[0] == '$':
            # socket queue协议, $开头的参数是变长参数
            args.append(param_str[1:])
        else:
            split_param = param_str.split('=', 1)
            if len(split_param) == 2:
                key, value = split_param
                annotation = spec.annotations.get(key)
                if type(annotation) == type:
                    try:
                        value = annotation(value)
                    except Exception as e:
                        raise Exception("invalid param %s, expect %s, %s" % (key, spec.annotations[key], e))
                kwargs[key] = value
    return args, kwargs


async def handle_http_request(header: str, message) -> BaseResponse:
    """
    :param header: GET /hello.txt HTTP/1.1
    :param message:
    :return:
    """
    method, http_path, *_ = header.split()
    if method != 'GET':
        raise Exception("invalid http method %s" % method)
    http_path_match = _http_path_pattern.search(http_path)
    command_name = http_path_match.group('path')
    command: Command = _available_commands.get(command_name)
    if command is None:
        raise Exception("invalid command name %s" % command_name)
    args, kwargs = parse_command_args(command, http_path_match.group('query'), sep='&')
    ret = command(*args, **kwargs)
    if isinstance(ret, BaseResponse):
        return ret
    elif isinstance(ret, Coroutine):
        ret = await ret
    return HttpResponse(ret)


async def handle_queue_request(header: str, message: bytes) -> BaseResponse:
    command_name = header.strip()
    command: Command = _available_commands.get(command_name)
    if command is None:
        raise Exception("invalid command name %s" % command_name)
    message = message.strip(b'\r\n\r\n').decode()
    args, kwargs = parse_command_args(command, message, sep='\r\n')
    ret = command(*args, **kwargs)
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
    # print("connect from ", writer.get_extra_info('peername'))
    try:
        header = await asyncio.wait_for(reader.readline(), timeout=5)
    except asyncio.TimeoutError:
        response = Response("read timeout on server", status=408)
    except Exception as e:
        response = Response(str(e), status=500)
    else:
        header = header.decode()
        if _http_header_pattern.match(header):
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


async def run_cache_manager():
    # 每隔n秒检查一次缓存, 如果缓存过期则删除
    while True:
        await asyncio.sleep(1)
        expired_keys = []
        for k, v in _cache_mapping.items():
            if isinstance(v, TTLString) and v.expired:
                expired_keys.append(k)
            # 不能用del, 因为在遍历的时候不能删除
        for k in expired_keys:
            del _cache_mapping[k]


async def main():
    import socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    server_socket.bind(('127.0.0.1', 55555))
    server = await asyncio.start_server(handle_client, sock=server_socket)
    addr = server_socket.getsockname()
    print(f'Cacheing Serving on {addr}')
    await run_cache_manager()
    async with server:
        await server.serve_forever()


def start_cache_service():
    asyncio.run(main())


def ensure_server_running():
    try:
        cache_agent.ping()
    except ConnectionRefusedError:
        from multiprocessing import Process, set_start_method
        set_start_method('spawn', force=True)
        p = Process(target=start_cache_service, daemon=False)
        p.start()


django_settings_module = os.environ.get('DJANGO_SETTINGS_MODULE')
CACHE_SERVICE = None
if django_settings_module:
    settings = importlib.import_module(django_settings_module)
    CACHE_SERVICE = getattr(settings, 'CACHE_SERVICE', None)
if CACHE_SERVICE is None:
    CACHE_SERVICE = {
        'engine': 'socket',
        'config': {
            'host': '127.0.0.1',
            'port': 55555,
        }
    }


class CacheAgent:
    def __init__(self, host='127.0.0.1', port=55555):
        self.host = host
        self.port = port

    # def connect(self):
    #     self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #     self._socket.connect((self.host, self.port))
    #     self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

    # def close(self):
    #     self._socket.close()

    def execute(self, command, *args: List[str], **kwargs):
        _socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _socket.connect((self.host, self.port))
        command_lines = [command]
        for k, v in kwargs.items():
            if isinstance(v, dict):
                v = json.dumps(v, ensure_ascii=False)
            command_lines.append(f"{k}={v}")
        for arg in args:
            command_lines.append(f'${arg}')
        message = f'\r\n'.join(command_lines) + '\r\n\r\n'
        _socket.send(message.encode())
        data = _socket.recv(4096)
        while not data.endswith(b'\r\n\r\n'):
            data += _socket.recv(4096)
        _socket.close()
        data = data.strip(b'\r\n').decode()
        if data[0] == '-':
            raise Exception(data[1:])
        elif data == '*-1':
            return None
        elif data[0] == '+':
            return data[1:]
        return data

    def llen(self, key):
        return int(self.execute('llen', qname=key))

    def set(self, key, value, expire=0):
        return self.execute('set', key, value, expire=expire)

    def mset(self, scope=None, expire=0, **kwargs):
        if scope:
            kwargs = {f'{scope}:{k}': v for k, v in kwargs.items()}
        return self.execute('mset', expire=expire, data=kwargs)

    def get(self, key):
        return self.execute('get', key)

    def delete(self, key):
        return self.execute('delete', key)

    def qpush(self, key, *value):
        return self.execute('qpush', *value, qname=key)

    def qpop(self, key):
        return self.execute('qpop', qname=key)

    def qbpop(self, key, timeout=0):
        return self.execute('qbpop', qname=key, timeout=timeout)

    def push(self, key, *value):
        return self.execute('push', *value, name=key)

    def pop(self, key):
        return self.execute('pop', name=key)

    def bpop(self, key, timeout=0):
        return self.execute('bpop', name=key, timeout=timeout)

    def list(self):
        return self.execute('list')

    def hset(self, name, key: Optional[str] = None,
             value: Optional[str] = None, mapping: Optional[Dict[str, str]] = None, **kwargs):
        data = mapping or {}
        data.update(kwargs)
        if key and value:
            data[key] = value
        return self.execute('hset', name, data=data)

    def hget(self, name, key):
        return self.execute('hget', name, key)

    def hgetall(self, name):
        item = self.execute('hgetall', name)
        if item is not None:
            item = json.loads(item)
        return item

    def hdel(self, name, key):
        return self.execute('hdel', name, key)

    def ping(self):
        _socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _socket.connect((self.host, self.port))
        _socket.close()


class Key(str):
    pass


class MapKey(str):
    pass


class ListKey(str):
    pass


class CacheState(dict):
    def __init__(self, key: Union[MapKey, Key, ListKey]):
        super(CacheState, self).__init__()
        self.key = key

    def __setattr__(self, key, value):
        self[key] = value
        super(CacheState, self).__setattr__(key, value)

    def commit(self, **kwargs) -> dict:
        for k, v in kwargs.items():
            setattr(self, k, v)
        return kwargs or self

    def push(self, **kwargs):
        raise NotImplementedError

    def commit_and_push(self, **kwargs):
        if isinstance(self.key, Key):
            return self.push(**self.commit(**kwargs))
        else:
            self.commit(**kwargs)
            return self.push(**self)

    def pull(self):
        raise NotImplementedError

    def delete(self):
        raise NotImplementedError


def ensure_service_available():
    if CACHE_SERVICE['engine'] == 'redis':
        import redis
        try:
            cache_agent.ping()
        except redis.exceptions.ConnectionError:
            raise Exception('redis connection error with config %s' % CACHE_SERVICE['config'])
    elif CACHE_SERVICE['engine'] == 'socket':
        ensure_server_running()
    else:
        raise Exception('invalid cache server engine %s' % CACHE_SERVICE['engine'])


if CACHE_SERVICE['engine'] == 'redis':
    import redis
    pool = redis.ConnectionPool(**CACHE_SERVICE['config'])
    cache_agent = redis.Redis(connection_pool=pool)
else:
    cache_agent = CacheAgent(**CACHE_SERVICE['config'])


if __name__ == '__main__':
    start_cache_service()
