import inspect
from datetime import timedelta
from functools import wraps
from typing import Any, Final

from mongoengine import DateTimeField, Document, DynamicField, StringField

from nomad.common import now

MAX_MONGO_CACHE_SIZE: Final[int] = 10 * 1024 * 1024  # 10 MiB
MONGO_CACHE_DEFAULT_TTL: Final[timedelta] = timedelta(hours=1)


class MongoCache(Document):
    """
    An arbitrary value to cache for fast retrieval.
    """

    key = StringField(required=True, unique=True)
    value = DynamicField()
    create_time = DateTimeField(default=now())
    expire_time = DateTimeField(required=True)

    meta = {
        'collection': 'cache',
        'indexes': [
            'key',
            {
                'fields': ['expire_time'],
                'expireAfterSeconds': 0,
            },
        ],
        'max_size': MAX_MONGO_CACHE_SIZE,
    }


def put_cached(key: str, ttl: timedelta, value: Any) -> Any:
    current = now()
    times = dict(create_time=current, expire_time=current + ttl)
    cached = MongoCache(key=key, value=value, **times)
    cached.save().reload()
    return cached


def get_cached(key: str) -> Any:
    return MongoCache.objects(key=key).get()


def cache(key: str, ttl: timedelta):
    def decorator(func):
        nonlocal key
        if key is None:
            key = f'{func.__module__}:{func.__qualname__}'

        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    cached = get_cached(key)
                except MongoCache.DoesNotExist:
                    value = await func(*args, **kwargs)
                    cached = put_cached(key, ttl, value)
                return cached.value

            return async_wrapper

        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                try:
                    cached = MongoCache.objects(key=key).get()
                except MongoCache.DoesNotExist:
                    value = func(*args, **kwargs)
                    cached = put_cached(key, ttl, value)
                return cached.value

            return sync_wrapper

    return decorator
