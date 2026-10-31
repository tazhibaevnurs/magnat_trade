"""Redis cache with LocMem fallback when Redis is unreachable."""

from __future__ import annotations

import logging

from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.core.cache.backends.locmem import LocMemCache
from django.core.cache.backends.redis import RedisCache

logger = logging.getLogger(__name__)


def _redis_errors() -> tuple[type[BaseException], ...]:
    from redis.exceptions import ConnectionError, TimeoutError

    return (ConnectionError, TimeoutError, OSError)


class ResilientRedisCache(RedisCache):
    """
    Production cache: prefer Redis, but never take down HTTP requests if Redis is down.
    Celery still requires a healthy Redis broker separately.
    """

    def __init__(self, server, params):
        super().__init__(server, params)
        self._fallback = LocMemCache("resilient-redis-fallback", params)

    def _try_primary(self, op: str, primary, fallback):
        try:
            return primary()
        except _redis_errors() as exc:
            logger.warning("Redis cache %s failed (%s); using LocMem fallback", op, exc)
            return fallback()

    def get(self, key, default=None, version=None):
        def primary():
            return RedisCache.get(self, key, default=default, version=version)

        def fallback():
            return self._fallback.get(key, default=default, version=version)

        return self._try_primary("get", primary, fallback)

    def set(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        def primary():
            return RedisCache.set(self, key, value, timeout=timeout, version=version)

        def fallback():
            return self._fallback.set(key, value, timeout=timeout, version=version)

        return self._try_primary("set", primary, fallback)

    def add(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        def primary():
            return RedisCache.add(self, key, value, timeout=timeout, version=version)

        def fallback():
            return self._fallback.add(key, value, timeout=timeout, version=version)

        return self._try_primary("add", primary, fallback)

    def delete(self, key, version=None):
        def primary():
            return RedisCache.delete(self, key, version=version)

        def fallback():
            return self._fallback.delete(key, version=version)

        return self._try_primary("delete", primary, fallback)

    def has_key(self, key, version=None):
        def primary():
            return RedisCache.has_key(self, key, version=version)

        def fallback():
            return self._fallback.has_key(key, version=version)

        return self._try_primary("has_key", primary, fallback)

    def incr(self, key, delta=1, version=None):
        def primary():
            return RedisCache.incr(self, key, delta=delta, version=version)

        def fallback():
            return self._fallback.incr(key, delta=delta, version=version)

        return self._try_primary("incr", primary, fallback)

    def decr(self, key, delta=1, version=None):
        def primary():
            return RedisCache.decr(self, key, delta=delta, version=version)

        def fallback():
            return self._fallback.decr(key, delta=delta, version=version)

        return self._try_primary("decr", primary, fallback)

    def touch(self, key, timeout=DEFAULT_TIMEOUT, version=None):
        def primary():
            return RedisCache.touch(self, key, timeout=timeout, version=version)

        def fallback():
            return self._fallback.touch(key, timeout=timeout, version=version)

        return self._try_primary("touch", primary, fallback)

    def clear(self):
        self._fallback.clear()

        def primary():
            return RedisCache.clear(self)

        return self._try_primary("clear", primary, lambda: None)
