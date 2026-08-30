import redis
import os

# Get Redis URL from environment or default to local
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

try:
    # Initialize Redis client with a short timeout so it doesn't hang
    redis_client = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
    # Test connection
    redis_client.ping()
except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
    # Fallback mock client if Redis is not running locally
    print("WARNING: Redis server not detected. Token blacklisting/caching will use memory fallback.")
    
    class DummyRedis:
        def __init__(self):
            self.store = {}
        def set(self, name, value, ex=None, *args, **kwargs): 
            self.store[name] = value
            return True
        def get(self, name, *args, **kwargs): 
            return self.store.get(name)
        def exists(self, name, *args, **kwargs): 
            return 1 if name in self.store else 0
        def delete(self, name, *args, **kwargs): 
            if name in self.store:
                del self.store[name]
            return True
        def ping(self): 
            return False
    
    redis_client = DummyRedis()


# --- Helper functions required by auth router ---

def blacklist_token(token: str, expire_seconds: int = 86400):
    """Add a token to the blacklist (with expiration matching token lifetime)."""
    redis_client.set(f"blacklist:{token}", "revoked", ex=expire_seconds)


def is_token_blacklisted(token: str) -> bool:
    """Check if a token has been blacklisted (revoked on logout)."""
    return bool(redis_client.exists(f"blacklist:{token}"))