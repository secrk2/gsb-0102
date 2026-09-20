import os


class Settings:
    # compose 中为 mysql+pymysql://huitang:huitang@mysql:3306/huitang?charset=utf8mb4
    DATABASE_URL = os.getenv(
        "DATABASE_URL", "mysql+pymysql://huitang:huitang@127.0.0.1:3306/huitang?charset=utf8mb4"
    )
    # memory:// 表示进程内实现（本地/测试用），生产走 redis://redis:6379/0
    REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    SEED_ON_START = os.getenv("SEED_ON_START", "true").lower() == "true"
    # 档期缓存秒数
    SCHEDULE_CACHE_TTL = int(os.getenv("SCHEDULE_CACHE_TTL", "60"))


settings = Settings()
