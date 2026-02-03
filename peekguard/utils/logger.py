import logging
from sys import stdout

logging.basicConfig(
    stream=stdout,
    format="[%(asctime)s] %(levelname)s %(module)s:%(lineno)d: %(message)s",
    level=logging.ERROR,
)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    return logger
