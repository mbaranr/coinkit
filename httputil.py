from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_TIMEOUT = 20

# Retry on transient server errors and connection failures.
# Backoff: 0.5s, 1s, 2s before giving up (1.5s wall time worst-case).
# Polling runs every 5 min, so this stays well within the cycle.
_RETRY = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=(500, 502, 503, 504),
    allowed_methods=("GET", "POST"),
    raise_on_status=False,
)

_session = requests.Session()
_adapter = HTTPAdapter(max_retries=_RETRY)
_session.mount("http://", _adapter)
_session.mount("https://", _adapter)


def get_json(url: str, *, timeout: float = DEFAULT_TIMEOUT, **kwargs) -> Any:
    r = _session.get(url, timeout=timeout, **kwargs)
    r.raise_for_status()
    return r.json()


def post_json(url: str, *, json: Any = None, timeout: float = DEFAULT_TIMEOUT, **kwargs) -> Any:
    r = _session.post(url, json=json, timeout=timeout, **kwargs)
    r.raise_for_status()
    return r.json()


def to_float(x: Any) -> float:
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        return float(x)
    raise TypeError(f"Cannot convert to float: {x}")
