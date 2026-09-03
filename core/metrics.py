"""
Prometheus metrics instrumentation configuration for Higala Express.
Handles application performance tracking and metric endpoints.
"""

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

def setup_metrics(app: FastAPI) -> None:
    """
    Configures and exposes Prometheus metrics endpoint for the FastAPI application.
    Tracks HTTP request durations, status codes, and active connections.
    """
    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untracted=True,
        excluded_handlers=["/metrics", "/health", "/docs", "/redoc", "/openapi.json"],
    ).instrument(app).expose(
        app, 
        endpoint="/metrics", 
        include_in_schema=True,
        tags=["Monitoring"]
    )