"""
Structured JSON logging configuration for Higala Express.
Implements production-grade logging with context propagation.
"""

import json
import logging
import logging.config
from datetime import datetime
from typing import Any, Dict
import sys
from pythonjsonlogger import jsonlogger
import os

# Environment
ENV = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional context fields"""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        
        # Add standard fields
        log_record['timestamp'] = datetime.utcnow().isoformat()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno
        log_record['environment'] = ENV
        log_record['process_id'] = record.process
        log_record['thread_id'] = record.thread
        
        # Add exception info if present
        if record.exc_info:
            log_record['exception'] = self.format_exception(record.exc_info)
        
        # Add extra fields from logger
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id
        if hasattr(record, 'merchant_id'):
            log_record['merchant_id'] = record.merchant_id
    
    @staticmethod
    def format_exception(exc_info):
        """Format exception info"""
        import traceback
        return ''.join(traceback.format_exception(*exc_info))


def setup_logging():
    """Configure structured logging for the application"""
    
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
                "maxBytes": 10485760,  # 10MB
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
    
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Apply configuration
    logging.config.dictConfig(config)
    
    return logging.getLogger("higala")


# Initialize logger
logger = setup_logging()


class LogContext:
    """Context manager for adding extra fields to logs"""
    
    def __init__(self, **kwargs):
        self.fields = kwargs
        self.logger = logging.getLogger("higala")
    
    def __enter__(self):
        for key, value in self.fields.items():
            logging.LogRecord.__dict__[key] = value
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        for key in self.fields.keys():
            if key in logging.LogRecord.__dict__:
                del logging.LogRecord.__dict__[key]


def get_logger(module_name: str) -> logging.Logger:
    """Get a logger instance for a module"""
    return logging.getLogger(f"higala.{module_name}")
