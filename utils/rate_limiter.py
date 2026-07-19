"""
utils/rate_limiter.py

Simple rate limiter that sleeps for a random duration between min and max seconds.
Used between HTTP requests to the same domain to avoid hammering servers.
"""
import logging
import random
import time

logger = logging.getLogger(__name__)


def rate_limit_sleep(
    min_seconds: float = 1.5,
    max_seconds: float = 3.0,
    domain: str = "",
) -> None:
    """
    Sleep for a random duration between min_seconds and max_seconds.

    Args:
        min_seconds: Minimum sleep time.
        max_seconds: Maximum sleep time.
        domain: Optional domain name (for logging purposes).
    """
    delay = random.uniform(min_seconds, max_seconds)
    logger.debug(
        f"Rate limiting: sleeping {delay:.1f}s"
        + (f" for {domain}" if domain else "")
    )
    time.sleep(delay)
