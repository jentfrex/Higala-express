import hashlib
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import redis
import os

# Connect to Redis for idempotency store (adjust URL as needed)
redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Only enforce idempotency on state-changing methods
        if request.method in ["POST", "PUT", "PATCH"]:
            idempotency_key = request.headers.get("X-Idempotency-Key")
            if idempotency_key:
                cache_key = f"idempotency:{idempotency_key}"
                cached_response = redis_client.get(cache_key)
                
                if cached_response:
                    # Return cached response to prevent duplicate execution
                    parts = cached_response.split(b"|||")
                    status_code = int(parts[0])
                    body = parts[1]
                    return Response(content=body, status_code=status_code, media_type="application/json")
                
                # Execute request
                response = await call_next(request)
                
                # Cache successful or client-error responses
                if 200 <= response.status_code < 500:
                    response_body = b""
                    async for chunk in response.body_iterator:
                        response_body += chunk
                    
                    # Store response in Redis with 24-hour expiration
                    redis_client.setex(cache_key, 86400, f"{response.status_code}|||".encode() + response_body)
                    
                    return Response(content=response_body, status_code=response.status_code, headers=dict(response.headers), media_type=response.media_type)
                
                return response

        return await call_next(request)