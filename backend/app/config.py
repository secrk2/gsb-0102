import os


class Settings:
    # mysql+pymysql://user:pass@host:3306/dbname?charset=utf8mb4
    # sqlite:///./data.db 仅用于本地无 Docker 调试
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://huitang:huitang@mysql:3306/huitang?charset=utf8mb4",
    )
    # redis://host:6379/0 ；fakeredis:// 仅用于本地无二进制调试
    REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

    # 占用锁：一个场地同一时刻只允许一个下单请求进入临界区
    LOCK_TTL_SECONDS = int(os.getenv("LOCK_TTL_SECONDS", "10"))
    # 档期查询缓存
    SCHEDULE_CACHE_TTL_SECONDS = int(os.getenv("SCHEDULE_CACHE_TTL_SECONDS", "30"))


settings = Settings()
