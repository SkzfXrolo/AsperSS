from __future__ import annotations

import os
import time
import requests


def safe_http_post(url, data, timeout=30, retries=3, backoff_factor=0.5):
    proxies = None
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    if proxy:
        proxies = {"http": proxy, "https": proxy}
    last_exc = None
    for attempt in range(retries):
        try:
            r = requests.post(url, json=data, timeout=timeout, verify=True, proxies=proxies)
            return r
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(backoff_factor * (2 ** attempt))
    raise last_exc

