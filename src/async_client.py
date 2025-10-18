import asyncio
import random
import time
from typing import Any, Dict, Optional, Union

import aiohttp

class RateLimitError(Exception):
    pass

class AsyncHTTPClient:
    """
    Cliente HTTP assíncrono com:
    - Rate limiting simples (min interval entre chamadas)
    - Concorrência controlada via Semaphore 
    - Retries com backoff exponencial e jitter
    - Respeito ao Retry-After (se presente)
    """

    def __init__(
        self,
        base_url: str,
        headers: Optional[Dict[str, str]] = None,
        rate_per_minute: int = 60,
        concurrency: int = 4,
        request_timeout_sec: int = 30,
        max_retries: int = 5,
        name: str = "AsyncHTTPClient",
    ):
        self.base_url = base_url.rstrip("/")
        self._headers = headers or {}
        self._timeout = aiohttp.ClientTimeout(total=request_timeout_sec)
        self._session: Optional[aiohttp.ClientSession] = None
        self._sem = asyncio.Semaphore(concurrency)
        self._min_interval = 60.0 / max(1, rate_per_minute)
        self._last_call = 0.0
        self._lock = asyncio.Lock()
        self._max_retries = max_retries
        self._name = name

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(timeout=self._timeout, raise_for_status=False, headers=self._headers)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._session is not None:
            await self._session.close()

    async def _throttle(self):
        async with self._lock:
            elapsed = time.time() - self._last_call
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_call = time.time()

    def _build_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    async def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        expected_status: int = 200,
    ) -> aiohttp.ClientResponse:
        """
        Faz GET com retries/backoff.
        Retorna o objeto Response (já consumível via .json()) em sucesso.
        """
        url = self._build_url(path)
        attempt = 0
        last_exc: Optional[Exception] = None

        while attempt <= self._max_retries:
            attempt += 1
            async with self._sem:
                await self._throttle()
                try:
                    assert self._session is not None, "ClientSession não inicializado"
                    resp = await self._session.get(url, params=params, headers=headers)
                    # Trata 429 / 5xx com retry
                    if resp.status == expected_status:
                        return resp

                    # Se recebeu Retry-After, respeitar
                    if resp.status == 429:
                        retry_after = resp.headers.get("Retry-After")
                        delay = float(retry_after) if retry_after and retry_after.isdigit() else self._compute_backoff(attempt)
                        await resp.release()
                        await asyncio.sleep(delay)
                        continue

                    if 500 <= resp.status < 600:
                        await resp.release()
                        await asyncio.sleep(self._compute_backoff(attempt))
                        continue

                    # 4xx (exceto 429) e outros códigos: não retry
                    resp.raise_for_status()
                    return resp

                except (aiohttp.ServerDisconnectedError, aiohttp.ClientConnectionError, aiohttp.ClientPayloadError) as e:
                    last_exc = e
                    await asyncio.sleep(self._compute_backoff(attempt))
                except asyncio.TimeoutError as e:
                    last_exc = e
                    await asyncio.sleep(self._compute_backoff(attempt))

        # Estourou os retries
        if last_exc:
            raise last_exc
        raise RuntimeError(f"Falha ao requisitar {url} após {self._max_retries} tentativas.")

    async def get_json(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        expected_status: int = 200,
    ) -> Union[Dict[str, Any], Any]:
        resp = await self.get(path, params=params, headers=headers, expected_status=expected_status)
        # aiohttp precisa consumir o body; usar .json()
        try:
            return await resp.json(content_type=None)  # content_type=None para lidar com APIs que não setam corretamente
        finally:
            await resp.release()

    @staticmethod
    def _compute_backoff(attempt: int, base: float = 1.0, cap: float = 30.0) -> float:
        # Exponential backoff com jitter aleatório
        delay = min(cap, base * (2 ** (attempt - 1)))
        # jitter entre 0.5x e 1.5x
        return delay * random.uniform(0.5, 1.5)