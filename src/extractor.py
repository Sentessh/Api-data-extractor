# src/extractor.py
import logging
from typing import Iterable, Dict, Any, Callable, List
from .http_client import HTTPClient

logger = logging.getLogger(__name__)

class Extractor:
    def __init__(self, client: HTTPClient, page_param='page', size_param='limit', page_size=100):
        self.client = client
        self.page_param = page_param
        self.size_param = size_param
        self.page_size = page_size

    def extract_paginated(self, path: str, params: Dict[str,Any]=None, item_key: str = None) -> Iterable[Dict[str,Any]]:
        """
        Generic pagination by page number. Yields items.
        If the API uses cursor-based pagination, adapt to use next_token from response.
        item_key: JSON key that contains list of items (e.g. 'data' or 'results')
        """
        params = params.copy() if params else {}
        page = 1
        while True:
            params[self.page_param] = page
            params[self.size_param] = self.page_size
            resp = self.client.get(path, params=params)
            j = resp.json()
            # try to find list of items
            if item_key:
                items = j.get(item_key, [])
            else:
                # heuristics: find first list in json
                items = None
                for v in j.values() if isinstance(j, dict) else []:
                    if isinstance(v, list):
                        items = v
                        break
                if items is None:
                    # fallback: if response is a list
                    if isinstance(j, list):
                        items = j
                    else:
                        items = []
            if not items:
                logger.debug(f"No items returned on page {page}, stopping.")
                break
            for item in items:
                yield item
            # stop condition: less than page_size or explicit last_page
            if len(items) < self.page_size:
                break
            page += 1

    # Example for cursor-based:
    def extract_cursor(self, path: str, params: Dict[str,Any]=None, cursor_field='next') -> Iterable[Dict[str,Any]]:
        params = params.copy() if params else {}
        cursor = None
        while True:
            if cursor:
                params['cursor'] = cursor
            resp = self.client.get(path, params=params)
            j = resp.json()
            items = j.get('data', []) or j.get('results', []) or (j if isinstance(j, list) else [])
            for item in items:
                yield item
            cursor = j.get(cursor_field)
            if not cursor:
                break