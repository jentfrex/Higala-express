import asyncio
from arq.connections import RedisSettings
from config import settings  # <--- Siguruha nga naa kini

async def send_notification_task(ctx, user_id: int, message: str):
    """Simulate sending an SMS or push notification."""
    await asyncio.sleep(2)
    print(f"Successfully sent notification to user {user_id}: {message}")
    return f"Notification sent to {user_id}"

class WorkerSettings:
    functions = [send_notification_task]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 10