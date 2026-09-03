"""
Structured JSON logging configuration for Higala Express.
Implements production-grade logging with context propagation.
"""

import json
import logging
import logging.config
from datetime import datetime, timezone
from typing import Any, Dict
import sys
import os
import contextvars
from pythonjsonlogger import jsonlogger

# Environment settings
ENV = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Context variable to hold contextual log data safely across async tasks and threads
_log_context: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar("_log_context", default={})

class ContextFilter(logging.Filter):
    """Custom filter to inject context variables safely into LogRecords"""
    def filter(self, record: logging.LogRecord) -> bool:
        context = _log_context.get()
        for key, value in context.items():
            setattr(record, key, value)
        return True


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional context fields"""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        
        # Add standard context fields
        log_record['timestamp'] = datetime.now(timezone.utc).isoformat()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno
        log_record['environment'] = ENV
        log_record['process_id'] = record.process
        log_record['thread_id'] = record.thread
        
        # Format exception tracebacks automatically if present
        if record.exc_info:
            log_record['exception'] = self.format_exception(record.exc_info)
        
        # Safely pass context IDs when using extra={...} or via LogContext
        for attr in ['user_id', 'request_id', 'merchant_id', 'driver_id']:
            if hasattr(record, attr):
                log_record[attr] = getattr(record, attr)
                
        # Include any dynamic keys from contextvars
        context = _log_context.get()
        for key, value in context.items():
            if key not in log_record:
                log_record[key] = value
    
    @staticmethod
    def format_exception(exc_info):
        """Format exception info into string"""
        import traceback
        return ''.join(traceback.format_exception(*exc_info))


def setup_logging():
    """Configure structured logging for the application"""
    
    # Ensure logs folder exists before initializing file handlers
    os.makedirs("logs", exist_ok=True)

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": CustomJsonFormatter,
                "format": "%(timestamp)s %(level)s %(name)s %(message)s"
            },
            "standard": {
                "format": "[%(asctime)s] %(levelname)s - %(name)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": LOG_LEVEL,
                "formatter": "json" if ENV == "production" else "standard",
                "stream": "ext://sys.stdout"
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": LOG_LEVEL,
                "formatter": "json",
                "filename": f"logs/higala-{ENV}.log",
                "maxBytes": 10485760,  # 10MB per log file
                "backupCount": 10,
                "encoding": "utf-8"
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "json",
                "filename": f"logs/higala-errors-{ENV}.log",
                "maxBytes": 10485760,
                "backupCount": 10,
                "encoding": "utf-8"
            }
        },
        "loggers": {
            "higala": {
                "level": LOG_LEVEL,
                "handlers": ["console", "file", "error_file"],
                "propagate": False
            },
            "higala.auth": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False
            },
            "higala.payment": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False
            },
            "higala.orders": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False
            },
            "higala.webhooks": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False
            },
            "higala.inventory": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False
            },
            "sqlalchemy.engine": {
                "level": "WARNING" if ENV == "production" else "DEBUG",
                "handlers": ["console", "file"],
                "propagate": False
            }
        },
        "root": {
            "level": LOG_LEVEL,
            "handlers": ["console", "file", "error_file"]
        }
    }
    
    # Load dictionary configuration
    logging.config.dictConfig(config)
    
    return logging.getLogger("higala")


# Global base logger instance
logger = setup_logging()


class LogContext:
    """Async/Thread-safe context manager for appending temporary metadata to execution blocks"""
    
    def __init__(self, **kwargs):
        self.fields = kwargs
        self.token = None
    
    def __enter__(self):
        current = _log_context.get().copy()
        current.update(self.fields)
        self.token = _log_context.set(current)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token:
            _log_context.reset(self.token)


def get_logger(module_name: str) -> logging.Logger:
    """Utility function to retrieve scoped module loggers with thread-safe context support"""
    logger_instance = logging.getLogger(f"higala.{module_name}")
    
    # Ensure the ContextFilter is added only once
    if not any(isinstance(f, ContextFilter) for f in logger_instance.filters):
        logger_instance.addFilter(ContextFilter())
        
    return logger_instance