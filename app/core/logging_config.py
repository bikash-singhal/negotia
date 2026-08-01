from logging.config import dictConfig

from app.core.observability import StructuredContextFilter


def configure_logging(debug: bool = False) -> None:
    log_level = "DEBUG" if debug else "INFO"

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "structured_context": {
                    "()": StructuredContextFilter,
                },
            },
            "formatters": {
                "default": {
                    "format": (
                        "%(asctime)s | %(levelname)s | %(name)s | "
                        "request_id=%(request_id)s | event=%(event)s | "
                        "operation=%(operation)s | route=%(route)s | "
                        "session_id=%(session_id)s | stage=%(stage)s | "
                        "provider=%(provider)s | model_id=%(model_id)s | "
                        "duration_ms=%(duration_ms)s | outcome=%(outcome)s | "
                        "output_length=%(output_length)s | "
                        "fence_detected=%(fence_detected)s | "
                        "failure_category=%(failure_category)s | "
                        "%(message)s"
                    ),
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "filters": ["structured_context"],
                    "level": log_level,
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "handlers": ["console"],
                "level": log_level,
            },
            "loggers": {
                "uvicorn.access": {
                    "handlers": ["console"],
                    "level": "INFO",
                    "propagate": False,
                },
                "uvicorn.error": {
                    "handlers": ["console"],
                    "level": "INFO",
                    "propagate": False,
                },
            },
        }
    )
