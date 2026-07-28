from logging.config import dictConfig


def configure_logging(debug: bool = False) -> None:
    log_level = "DEBUG" if debug else "INFO"

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
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
