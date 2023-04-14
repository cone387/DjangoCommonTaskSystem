import redis
import json
from queue import Empty


class RedisListQueue:

    required_params = {
        'host': {
            'type': str,
            'default': '127.0.0.1',
            'required': False,
        },
        'port': {
            'type': int,
            'default': 6379,
            'required': False,
        },
        'db': {
            'type': int,
            'default': 0,
            'required': False,
        },
        'password': {
            'type': str,
            'default': None,
            'required': False,
        },
    }

    def __init__(self, name=None, **kwargs):
        config = self.get_default_config()
        config.update(kwargs)
        self.config = config
        self.name = name
        self._redis = redis.Redis(**config)

    def get(self, block=True, timeout=0):
        if block:
            return self._redis.blpop(self.name, timeout=timeout)[1]
        return self.get_nowait()

    def get_nowait(self):
        o = self._redis.lpop(self.name)
        if o is None:
            raise Empty
        return json.loads(o)

    def put(self, item):
        return self._redis.rpush(self.name, json.dumps(item, ensure_ascii=False))

    def qsize(self):
        return self._redis.llen(self.name)

    def empty(self):
        return self.qsize() == 0

    def full(self):
        return False

    def validate(self):
        try:
            self._redis.ping()
            return ""
        except redis.exceptions.ConnectionError:
            return "%s connection error with config %s" % (self.__class__.__name__, self.config)
        except Exception as e:
            return str(e)

    @classmethod
    def validate_config(cls, config):
        for k, v in cls.required_params.items():
            if v.get('required', True) and k not in config:
                return "Missing required param: %s" % k
            if k in config and not isinstance(config[k], v['type']):
                return "Param %s should be %s" % (k, v['type'].__name__)
        return ""

    @classmethod
    def get_default_config(cls):
        return {k: v['default'] for k, v in cls.required_params.items()}
