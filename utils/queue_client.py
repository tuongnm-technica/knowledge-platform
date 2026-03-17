import arq
from arq.connections import RedisSettings

from config.settings import settings

_redis_pool = None

async def get_redis_pool() -> arq.ArqRedis:
    """Khởi tạo Singleton Redis Pool cho việc đẩy Task vào Queue"""
    global _redis_pool
    if not _redis_pool:
        redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
        _redis_pool = await arq.create_pool(redis_settings)
    return _redis_pool