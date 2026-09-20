"""Redis 客户端封装：占用分布式锁 + 档期查询缓存。

REDIS_URL=memory:// 时使用进程内实现，便于本地与测试运行；
compose 环境连接真正的 Redis。
"""
import fnmatch
import threading
import time
import uuid
from contextlib import contextmanager

import redis as redis_lib

from .config import settings


class _MemoryRedis:
    """最小化的内存实现：字符串 KV（带 TTL）+ 简易互斥锁。"""

    def __init__(self):
        self._kv = {}
        self._locks = {}
        self._cond = threading.Condition()

    def get(self, key):
        with self._cond:
            item = self._kv.get(key)
            if item is None:
                return None
            value, expire_at = item
            if expire_at and expire_at < time.time():
                self._kv.pop(key, None)
                return None
            return value

    def set(self, key, value, ex=None, nx=False):
        with self._cond:
            if nx and key in self._kv:
                old = self._kv[key]
                if not (old[1] and old[1] < time.time()):
                    return None
            expire_at = time.time() + ex if ex else None
            self._kv[key] = (value, expire_at)
            return True

    def delete(self, *keys):
        with self._cond:
            n = 0
            for key in keys:
                if self._kv.pop(key, None) is not None:
                    n += 1
            return n

    def scan_delete(self, pattern):
        """按 glob 模式批量删除（缓存失效用）。"""
        with self._cond:
            n = 0
            for key in list(self._kv.keys()):
                if fnmatch.fnmatch(key, pattern):
                    self._kv.pop(key, None)
                    n += 1
            return n


class KVStore:
    def __init__(self, url: str):
        self.url = url
        if url.startswith("memory"):
            self._mem = _MemoryRedis()
            self._client = None
        else:
            self._mem = None
            self._client = redis_lib.Redis.from_url(url, decode_responses=True)

    def ping(self):
        if self._mem:
            return True
        return self._client.ping()

    # ---------- 字符串缓存 ----------
    def cache_get(self, key):
        if self._mem:
            raw = self._mem.get(key)
            return raw.decode() if raw is not None else None
        return self._client.get(key)

    def cache_set(self, key, value, ttl):
        if self._mem:
            self._mem.set(key, value.encode("utf-8"), ex=ttl)
        else:
            self._client.set(key, value, ex=ttl)

    def invalidate_pattern(self, pattern):
        if self._mem:
            return self._mem.scan_delete(pattern)
        # Redis：scan + 批量删
        n = 0
        for key in self._client.scan_iter(match=pattern, count=200):
            self._client.delete(key)
            n += 1
        return n

    # ---------- 占用锁 ----------
    @contextmanager
    def venue_lock(self, venue_id: int, timeout: float = 5.0):
        """对单个场地加分布式锁，保证“查重 + 写入”原子。

        撞锁（有人正在同时下单）时等待重试；拿到锁后执行业务，
        finally 中用 token 校验后释放，避免误删别人的锁。
        """
        key = f"lock:venue:{venue_id}"
        token = uuid.uuid4().hex
        if self._mem:
            cond = self._mem._cond
            with cond:
                deadline = time.time() + timeout
                while key in self._mem._locks and time.time() < deadline:
                    cond.wait(timeout - (deadline - time.time()))
                if key in self._mem._locks:
                    raise TimeoutError(f"场地 {venue_id} 正忙，请稍后重试")
                self._mem._locks[key] = token
            try:
                yield
            finally:
                with cond:
                    if self._mem._locks.get(key) == token:
                        self._mem._locks.pop(key, None)
                        cond.notify_all()
            return

        got = self._client.set(key, token, nx=True, ex=int(timeout) + 1)
        deadline = time.time() + timeout
        while not got and time.time() < deadline:
            time.sleep(0.05)
            got = self._client.set(key, token, nx=True, ex=int(timeout) + 1)
        if not got:
            raise TimeoutError(f"场地 {venue_id} 正忙，请稍后重试")
        try:
            yield
        finally:
            # compare-and-delete：只释放自己的锁
            self._client.eval(
                "if redis.call('get', KEYS[1]) == ARGV[1] "
                "then return redis.call('del', KEYS[1]) else return 0 end",
                1,
                key,
                token,
            )


kv = KVStore(settings.REDIS_URL)
