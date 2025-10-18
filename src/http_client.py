# src/http_client.py
import time
import logging
from typing import Dict, Any, Optional
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class RateLimitException(Exception):
    pass

class HTTPClient:
    def __init__(self, base_url: str, headers: Dict[str,str] = None, rate_per_minute: int = 60, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        if headers:
            self.session.headers.update(headers)
        self.rate_per_minute = rate_per_minute
        self.min_interval = 60.0 / max(1, rate_per_minute)
        self._last_call = 0.0
        self.timeout = timeout

    def _throttle(self):
        elapsed = time.time() - self._last_call
        if elapsed < self.min_interval:
            wait = self.min_interval - elapsed
            logger.debug(f"Throttling: sleeping {wait:.2f}s to respect rate limit")
            time.sleep(wait)

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=30),
           retry=retry_if_exception_type((requests.exceptions.RequestException, RateLimitException)))
    def get(self, path: str, params: Dict[str,Any] = None, headers: Dict[str,str] = None) -> requests.Response:
        self._throttle()
        url = f"{self.base_url}/{path.lstrip('/')}"
        logger.debug(f"GET {url} params={params}")
        resp = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
        self._last_call = time.time()
        if resp.status_code == 429:
            # rate limit from server — raise for retry and exponential backoff
            raise RateLimitException("429 Too Many Requests")
        resp.raise_for_status()
        return resp