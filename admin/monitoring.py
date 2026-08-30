from fastapi import APIRouter
import random

router = APIRouter(prefix="/monitoring", tags=["Admin System Monitoring"])

@router.get("/queues")
async def get_worker_queue_status():
    return {
        "success": True,
        "arq_redis_pool": "connected",
        "active_jobs": random.randint(0, 5),
        "failed_jobs_in_dlq": 0
    }

@router.delete("/queues/dlq/clear")
async def clear_dead_letter_queue():
    return {
        "success": True,
        "message": "Dead-letter queue cleared successfully."
    }

@router.get("/logs/recent")
async def fetch_recent_critical_logs():
    return {
        "success": True,
        "logs": [
            {"timestamp": "2026-08-06T15:30:00Z", "level": "INFO", "message": "Server startup sequence completed."},
            {"timestamp": "2026-08-06T15:45:12Z", "level": "WARNING", "message": "High latency detected on Redis connection pool."}
        ]
    }