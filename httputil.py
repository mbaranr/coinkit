from typing import Any

import requests


DEFAULT_TIMEOUT = 20


def get_json(url: str, *, timeout: float = DEFAULT_TIMEOUT, **kwargs) -> Any:
    r = requests.get(url, timeout=timeout, **kwargs)
    r.raise_for_status()
    return r.json()


def post_json(url: str, *, json: Any = None, timeout: float = DEFAULT_TIMEOUT, **kwargs) -> Any:
    r = requests.post(url, json=json, timeout=timeout, **kwargs)
    r.raise_for_status()
    return r.json()


def to_float(x: Any) -> float:
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        return float(x)
    raise TypeError(f"Cannot convert to float: {x}")
