"""Redis 客户端：占用锁 + 档期缓存。

REDIS_URL=fakeredis:// 时使用纯 Python 的 fakeredis，仅供无 Redis 二进制的
本地调试；compose 部署始终连接真实 Redis。

锁释放用 WATCH 事务而非 Lua（fakeredis 默认不带 Lua 引擎，真 Redis 下两者
安全性等价：只删自己持有的 token）。
"""

import redis

from .config import settings

if settings.REDIS_URL.startswith("fakeredis://"):
    import fakeredis

    client = fakeredis.FakeRedis(decode_responses=True)
else:
    client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def release_lock(key: str, token: str) -> bool:
    """只在锁仍属于本 token 时删除，返回是否释放成功。"""
    pipe = client.pipeline()
    try:
        pipe.watch(key)
        if pipe.get(key) != token:
            pipe.unwatch()
            return False
        pipe.multi()
        pipe.delete(key)
        pipe.execute()
        return True
    except redis.WatchError:
        return False
