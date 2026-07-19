"""
utils/http_client.py

A pre-configured requests Session wrapper with:
- Custom User-Agent header
- Automatic retries with exponential backoff
- Configurable timeout
"""
import logging

import requests
from requests.adapters import HTTPAdapter, Retry
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


def create_http_session(
    user_agent: str = "JobSearchBot/1.0",
    timeout: int = 15,
) -> requests.Session:
    """
    Create a requests Session with default headers and retry adapter.

    Args:
        user_agent: User-Agent string to include in all requests.
        timeout: Default timeout in seconds.

    Returns:
        Configured requests.Session instance.
    """
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.5",
        }
    )

    # Mount retry adapter for transient HTTP errors
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    reraise=True,
)
def fetch_url(
    url: str,
    session: requests.Session = None,
    timeout: int = 15,
) -> str:
    """
    Fetch a URL and return the response text.

    Args:
        url: URL to fetch.
        session: Optional pre-configured session. Creates one if not provided.
        timeout: Request timeout in seconds.

    Returns:
        Response text content.

    Raises:
        requests.exceptions.HTTPError: On non-2xx status codes.
    """
    if session is None:
        session = create_http_session()

    resp = session.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text
