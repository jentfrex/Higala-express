import os
import time
import logging
import redis

logger = logging.getLogger("higala.redis")

# Get Redis URL from environment or default to local
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

class DummyRedis:
    """Synchronous mock Redis client for local development when Redis server is down"""
    def __init__(self):
        self.store = {}
        self.expiry = {}
        logger.warning("Using DummyRedis memory store (Redis server not detected).")

    def set(self, name, value, ex=None, *args, **kwargs):
        self.store[name] = value
        if ex is not None:
            self.expiry[name] = time.time() + float(ex)
        elif name in self.expiry:
            del self.expiry[name]
        return True

    def get(self, name, *args, **kwargs):
        if name in self.expiry and time.time() > self.expiry[name]:
            self.delete(name)
            return None
        return self.store.get(name)

    def exists(self, name, *args, **kwargs):
        if name in self.expiry and time.time() > self.expiry[name]:
            self.delete(name)
            return 0
        return 1 if name in self.store else 0

    def delete(self, name, *args, **kwargs):
        existed = False
        if name in self.store:
            del self.store[name]
            existed = True
        if name in self.expiry:
            del self.expiry[name]
        return 1 if existed else 0

    def ping(self):
        return True


# Initialize Redis client safely with fallback
try:
    redis_client = redis.from_url(
        REDIS_URL, 
        decode_responses=True, 
        socket_connect_timeout=2.0
    )
    # Test connection
    redis_client.ping()
    logger.info("Connected to Redis server successfully.")
except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError, Exception) as e:
    logger.warning(f"Redis server not detected ({e}). Token blacklisting/caching will use memory fallback.")
    redis_client = DummyRedis()


# --- Helper functions required by auth router ---

def blacklist_token(token: str, expire_seconds: int = 86400) -> None:
    """Add a token to the blacklist (with expiration matching token lifetime)."""
    try:
        redis_client.set(f"blacklist:{token}", "revoked", ex=expire_seconds)
    except Exception as e:
        logger.error(f"Failed to blacklist token: {e}")


def is_token_blacklisted(token: str) -> bool:
    """Check if a token has been blacklisted (revoked on logout)."""
    try:
        res = redis_client.exists(f"blacklist:{token}")
        return bool(res)
    except Exception as e:
        logger.error(f"Error checking token blacklist: {e}")
        return False