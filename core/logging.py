"""
Structured JSON logging configuration for Higala Express.
Implements production-grade logging with context propagation.
"""

import logging
import logging.config
from datetime import datetime, timezone
from typing import Any, Dict
import os
import contextvars

# --- Safe import across python-json-logger versions (old: jsonlogger.JsonFormatter,
# new 3.x+: pythonjsonlogger.json.JsonFormatter) ---
try:
    from pythonjsonlogger.json import JsonFormatter as _BaseJsonFormatter
except ImportError:
    try:
        from pythonjsonlogger import jsonlogger
        _BaseJsonFormatter = jsonlogger.JsonFormatter
    except ImportError:
        _BaseJsonFormatter = None  # falls back to plain formatting below

# Environment settings
ENV = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

_log_context: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar("_log_context", default={})


class ContextFilter(logging.Filter):
    """Custom filter to inject context variables safely into LogRecords"""
    def filter(self, record: logging.LogRecord) -> bool:
        context = _log_context.get()
        for key, value in context.items():
            setattr(record, key, value)
        return True


if _BaseJsonFormatter is not None:
    class CustomJsonFormatter(_BaseJsonFormatter):
        """Custom JSON formatter with additional context fields"""

        def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
            super().add_fields(log_record, record, message_dict)

            log_record['timestamp'] = datetime.now(timezone.utc).isoformat()
            log_record['level'] = record.levelname
            log_record['logger'] = record.name
            log_record['module'] = record.module
            log_record['function'] = record.funcName
            log_record['line'] = record.lineno
            log_record['environment'] = ENV
            log_record['process_id'] = record.process
            log_record['thread_id'] = record.thread

            if record.exc_info:
                log_record['exception'] = self.format_exception(record.exc_info)

            for attr in ['user_id', 'request_id', 'merchant_id', 'driver_id']:
                if hasattr(record, attr):
                    log_record[attr] = getattr(record, attr)

            context = _log_context.get()
            for key, value in context.items():
                if key not in log_record:
                    log_record[key] = value

        @staticmethod
        def format_exception(exc_info):
            import traceback
            return ''.join(traceback.format_exception(*exc_info))
else:
    # Fallback: plain text formatter if pythonjsonlogger isn't available at all
    CustomJsonFormatter = logging.Formatter


def _can_write_logs_dir() -> bool:
    """Check whether we can actually create/write to a local logs directory.
    Render's disk is usually writable, but this must never crash startup."""
    try:
        os.makedirs("logs", exist_ok=True)
        test_path = os.path.join("logs", ".write_test")
        with open(test_path, "w") as f:
            f.write("ok")
        os.remove(test_path)
        return True
    except Exception:
        return False


def setup_logging():
    """Configure structured logging for the application.
    Never raises — falls back to console-only logging if file logging
    isn't available, so a logging misconfiguration can never crash the app."""

    file_logging_enabled = _can_write_logs_dir()

    formatter_name = "json" if (ENV == "production" and _BaseJsonFormatter is not None) else "standard"

    handlers = {
        "console": {
            "class": "logging.StreamHandler",
            "level": LOG_LEVEL,
            "formatter": formatter_name,
            "stream": "ext://sys.stdout"
        }
    }

    active_handlers = ["console"]

    if file_logging_enabled:
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": LOG_LEVEL,
            "formatter": "json" if _BaseJsonFormatter is not None else "standard",
            "filename": f"logs/higala-{ENV}.log",
            "maxBytes": 10485760,
            "backupCount": 10,
            "encoding": "utf-8"
        }
        handlers["error_file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "ERROR",
            "formatter": "json" if _BaseJsonFormatter is not None else "standard",
            "filename": f"logs/higala-errors-{ENV}.log",
            "maxBytes": 10485760,
            "backupCount": 10,
            "encoding": "utf-8"
        }
        active_handlers = ["console", "file", "error_file"]

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": CustomJsonFormatter,
                "format": "%(timestamp)s %(level)s %(name)s %(message)s"
            } if _BaseJsonFormatter is not None else {
                "format": "[%(asctime)s] %(levelname)s - %(name)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "standard": {
                "format": "[%(asctime)s] %(levelname)s - %(name)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": handlers,
        "loggers": {
            "higala": {"level": LOG_LEVEL, "handlers": active_handlers, "propagate": False},
            "higala.auth": {"level": "INFO", "handlers": active_handlers, "propagate": False},
            "higala.payment": {"level": "INFO", "handlers": active_handlers, "propagate": False},
            "higala.orders": {"level": "INFO", "handlers": active_handlers, "propagate": False},
            "higala.webhooks": {"level": "INFO", "handlers": active_handlers, "propagate": False},
            "higala.inventory": {"level": "INFO", "handlers": active_handlers, "propagate": False},
            "sqlalchemy.engine": {
                "level": "WARNING" if ENV == "production" else "DEBUG",
                "handlers": active_handlers,
                "propagate": False
            }
        },
        "root": {"level": LOG_LEVEL, "handlers": active_handlers}
    }

    try:
        logging.config.dictConfig(config)
    except Exception as e:
        # Absolute last resort: basic console logging so the app can still start
        logging.basicConfig(level=LOG_LEVEL)
        logging.getLogger("higala").warning(f"Structured logging config failed, using basicConfig fallback: {e}")

    return logging.getLogger("higala")


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

    if not any(isinstance(f, ContextFilter) for f in logger_instance.filters):
        logger_instance.addFilter(ContextFilter())

    return logger_instance