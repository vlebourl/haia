"""Application entry point for HAIA Chat API server."""

import uvicorn

from haia.config import settings


def main():
    """Run the HAIA API server with uvicorn."""
    uvicorn.run(
        "haia.api.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,  # Set to True for development
        log_level="info",
    )


if __name__ == "__main__":
    main()
