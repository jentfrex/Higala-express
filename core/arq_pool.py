from arq import create_pool
from arq.connections import RedisSettings
from config import settings
import logging

logger = logging.getLogger(__name__)

arq_pool = None

async def init_arq_pool():
    global arq_pool
    try:
        # Use settings.REDIS_URL parsed natively via RedisSettings.from_dsn
        arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        logger.info("Redis background task pool initialized successfully.")
    except Exception as e:
        # Gracefully handle missing Redis without noisy error output
        arq_pool = None
        logger.warning(f"Redis is not available. Background tasks via ARQ will be disabled. ({e})")

async def close_arq_pool():
    global arq_pool
    if arq_pool:
        try:
            await arq_pool.close()
        except Exception:
            pass

def get_arq_pool():
    return arq_pool