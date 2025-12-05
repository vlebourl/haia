"""Application entry point for HAIA Chat API server."""

import uvicorn

from haia.config import settings


def main():
    """Run the HAIA API server with uvicorn.

    Production-ready configuration:
    - No hot reload
    - JSON log formatting
    - Access logging enabled
    - Configurable workers (default: 1 for single-instance deployment)
    """
    uvicorn.run(
        "haia.api.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
        access_log=True,
        # Use JSON log format in production for better parsing
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
                "access": {
                    "format": "%(asctime)s - %(levelname)s - %(client_addr)s - \"%(request_line)s\" %(status_code)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
                "access": {
                    "formatter": "access",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
            },
            "loggers": {
                "uvicorn": {"handlers": ["default"], "level": "INFO"},
                "uvicorn.error": {"level": "INFO"},
                "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
            },
        },
    )


if __name__ == "__main__":
    main()
