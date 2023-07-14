import time


_cache = {}

Empty = object()


def _get_func_fp(func, args, kwargs):
    key = '%s-%s-%s' % (func.__hash__(), args, kwargs)
    return key


def ttl_cache(ttl=600):
    def fun_decorator(func):
        def wrapper(*args, **kwargs):
            fp = _get_func_fp(func, args, kwargs)
            result, cache_time = _cache.get(fp, (Empty, 0))
            now = time.time()
            if result is Empty or now - cache_time > ttl:
                result = func(*args, **kwargs)
                _cache[fp] = result, now
            return result
        return wrapper
    return fun_decorator
