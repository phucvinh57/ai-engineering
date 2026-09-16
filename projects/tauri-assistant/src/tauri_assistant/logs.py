import logging
import sys

from loguru import logger


class InterceptHandler(logging.Handler):
    """Redirect stdlib logging records (e.g. uvicorn's) into loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def configure_logger() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        colorize=True,
        level="INFO",
        format=("<green>{time:HH:mm:ss}</green> <level>{level}</level> <level>{message}</level>"),
    )

    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
