import time
from collections.abc import Awaitable
from functools import wraps
from typing import Callable, LiteralString, ParamSpec, TypeVar

from statsd.client import StatsClient

from peekguard.utils.config import get_config
from peekguard.utils.logger import get_logger

logger = get_logger(__name__)

_statsd_client: StatsClient | None = None

P = ParamSpec("P")
T = TypeVar("T")


def init_statsd():
    """
    Initializes the StatsD client based on the environment configuration.
    This environment is either `nv_prod` or `sandbox`.
    """
    global _statsd_client

    _statsd_client = StatsClient(
        host=get_config("statsd.host"),
        port=get_config("statsd.port", coerce=int),
        prefix=get_config("app.type"),
    )
    logger.info(
        "statsd client initialized successfully",
    )


def incr(stat_name: str):
    """No-Op if statsd is not initialized"""
    if _statsd_client:
        _statsd_client.incr(stat_name)


def _timing(stat_name: str, time_taken_in_ms: float, rate: int):
    """Logs timing if statsd is not initialized"""
    if _statsd_client:
        _statsd_client.timing(stat_name, time_taken_in_ms, rate)
        return
    logger.info("Metric '%s' took %fms", stat_name, time_taken_in_ms)


def timing_to_statsd_async(stat_name: LiteralString):
    """
    Decorator for async function that measures the execution time of a function and sends the timing data to StatsD.
    The decorator wraps the target async function and measures the time taken for its execution. It then sends this timing data
    to the StatsD system with the specified `stat_name`. The execution time is recorded in milliseconds.
    """

    def decorator(func: Callable[P, Awaitable[T]]):
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                end_time = time.time()
                elapsed_time_ms = (end_time - start_time) * 1000.0
                _timing(stat_name, elapsed_time_ms, rate=1)

        return wrapper

    return decorator


def timing_to_statsd_sync(stat_name: LiteralString):
    """Sends execution time (in ms) of decorated function to statsd under `stat_name`"""

    def decorator(func: Callable[P, T]):
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed_time_in_ms = (time.perf_counter() - start_time) * 1000
            _timing(stat_name, elapsed_time_in_ms, rate=1)
            return result

        return wrapper

    return decorator
