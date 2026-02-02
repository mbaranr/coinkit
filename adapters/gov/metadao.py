import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from dateutil import parser as dtparser


URL = "https://www.idontbelieve.link/api/v3/queryCollection?src=initial_load"

PAYLOAD: Dict[str, Any] = {
    "clientType": "notion_app",
    "source": {
        "type": "collection",
        "id": "27eeb888-79cf-81b9-88d0-000b44f10b2c",
        "spaceId": "fe163126-0b1d-4f84-8d35-a3b3855bc1eb",
    },
    "collectionView": {
        "id": "27eeb888-79cf-81e2-8719-000c3ad62b00",
        "spaceId": "fe163126-0b1d-4f84-8d35-a3b3855bc1eb",
    },
    "loader": {
        "reducers": {
            "gallery_groups": {
                "type": "groups",
                "version": "v2",
                "groupBy": {
                    "sort": {"type": "manual"},
                    "type": "select",
                    "property": "Us=`",
                    "hideEmptyGroups": True,
                },
                "groupSortPreference": [
                    {"value": {"type": "select", "value": "Live ICOs"}, "hidden": True, "property": "Us=`"},
                    {"value": {"type": "select", "value": "Scheduled ICOs"}, "hidden": False, "property": "Us=`"},
                    {"value": {"type": "select", "value": "Announced-ICOs"}, "property": "Us=`"},
                    {"value": {"type": "select", "value": "Post-ICO"}, "hidden": False, "property": "Us=`"},
                    {"value": {"type": "select"}, "hidden": True, "property": "Us=`"},
                    {"value": {"type": "select", "value": "Past-ICO"}, "hidden": True, "property": "Us=`"},
                ],
                "limit": 200,
                "blockResults": {
                    "type": "independent",
                    "defaultLimit": 500,
                    "loadContentCover": True,
                    "groupOverrides": {},
                },
            }
        },
        "sort": [],
        "searchQuery": "",
        "userTimeZone": "Europe/Berlin",
    },
}

GROUP_PROP = "Us=`"   # group column
TITLE_PROP = "title"  # project name
ICO_TEXT_PROP = "cIAG"
TLDR_PROP = "=cT`"
GOALS_PROP = "QwBV"

LAUNCH_PREFIX_RE = re.compile(r"^\s*Launch Date:\s*", re.IGNORECASE)

logger = logging.getLogger(__name__)


def _post_json(url: str, payload: Dict[str, Any], *, timeout: int = 30) -> Dict[str, Any]:
    r = requests.post(
        url,
        json=payload,
        headers={"content-type": "application/json"},
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        raise RuntimeError("Unexpected response type (expected JSON object)")
    return data


def _richtext_to_str(v: Any) -> str:
    """
    Notion richtext arrays: [["text", [decorations...]], ...]
    """
    if not isinstance(v, list):
        return ""
    out: List[str] = []
    for part in v:
        if isinstance(part, list) and part:
            s = part[0]
            if isinstance(s, str):
                out.append(s)
    return "".join(out).strip()


def _prop_text(props: Dict[str, Any], key: str) -> Optional[str]:
    s = _richtext_to_str(props.get(key, []))
    return s or None


def _extract_links(prop: Any) -> List[str]:
    """
    Extract all hyperlinks from a Notion richtext property value.
    Links are stored as decorations like: ["Twitter", [["a","https://x.com/..."]]]
    """
    links: List[str] = []
    if not isinstance(prop, list):
        return links

    for part in prop:
        if not (isinstance(part, list) and len(part) >= 2):
            continue
        decorations = part[1]
        if not isinstance(decorations, list):
            continue
        for deco in decorations:
            if isinstance(deco, list) and len(deco) == 2 and deco[0] == "a" and isinstance(deco[1], str):
                links.append(deco[1])

    return links


def _extract_all_links(props: Dict[str, Any]) -> List[str]:
    links: List[str] = []
    for v in props.values():
        links.extend(_extract_links(v))

    # de-dup preserving order
    seen = set()
    out: List[str] = []
    for l in links:
        if l not in seen:
            seen.add(l)
            out.append(l)
    return out


def _find_notion_date(props: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Generic recursive search for Notion date decorations: ["d", {"start_date": ...}]
    Returns (start_date, end_date) as ISO-like strings, or (None, None).
    """

    def walk(x: Any) -> Optional[Tuple[Optional[str], Optional[str]]]:
        if isinstance(x, list):
            if (
                len(x) == 2
                and x[0] == "d"
                and isinstance(x[1], dict)
                and "start_date" in x[1]
            ):
                d = x[1]
                return (d.get("start_date"), d.get("end_date"))
            for v in x:
                r = walk(v)
                if r:
                    return r
        elif isinstance(x, dict):
            for v in x.values():
                r = walk(v)
                if r:
                    return r
        return None

    for v in props.values():
        r = walk(v)
        if r:
            return r
    return (None, None)


def _parse_launch_dt(text: Optional[str]) -> Optional[str]:
    """
    Accepts e.g. 'Launch Date: February 3rd at 18:30 UTC'
    Returns ISO string in UTC or None.
    """
    if not text:
        return None
    if "tba" in text.lower():
        return None

    t = LAUNCH_PREFIX_RE.sub("", text).strip()
    t = t.replace(" at ", " ")

    now = datetime.now(timezone.utc)
    default = datetime(now.year, 1, 1, tzinfo=timezone.utc)
    dt = dtparser.parse(t, default=default)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    # if year missing and inferred date already passed this year, assume next year.
    # (heuristic: if input text doesn't mention a year.)
    if dt.year == now.year and dt.date() < now.date() and "20" not in t:
        dt = dt.replace(year=now.year + 1)

    return dt.astimezone(timezone.utc).isoformat()


def _best_twitter_link(props: Dict[str, Any]) -> Optional[str]:
    links = _extract_all_links(props)
    x_links = [l for l in links if "x.com/" in l or "twitter.com/" in l]

    # prefer a tweet/article-like link first; else first profile-like link
    for l in x_links:
        if "/status/" in l or "/article/" in l:
            return l
    return x_links[0] if x_links else None


def _extract_scheduled_icos(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    blocks = data.get("recordMap", {}).get("block", {})
    if not isinstance(blocks, dict):
        return []

    out: List[Dict[str, Any]] = []

    for wrap in blocks.values():
        if not isinstance(wrap, dict):
            continue
        block = wrap.get("value", {})
        if not isinstance(block, dict):
            continue

        props = block.get("properties", {})
        if not isinstance(props, dict) or not props:
            continue

        if _prop_text(props, GROUP_PROP) != "Scheduled ICOs":
            continue

        project = _prop_text(props, TITLE_PROP)
        if not project:
            continue

        start_date, end_date = _find_notion_date(props)

        ico_text = _prop_text(props, ICO_TEXT_PROP)
        start = start_date or _parse_launch_dt(ico_text)

        out.append(
            {
                "project": project,
                "start_date": start,     
                "end_date": end_date,  
                "ico_text": ico_text,
                "tldr": _prop_text(props, TLDR_PROP),
                "fundraising_goals": _prop_text(props, GOALS_PROP),
                "twitter_link": _best_twitter_link(props),
                "block_id": block.get("id"),
            }
        )

    out.sort(key=lambda x: (x.get("start_date") is None, x.get("start_date") or ""))
    return out


def fetch() -> List[Dict[str, Any]]:
    """
    Fetch MetaDAO scheduled ICO entries (as structured JSON) from the Notion-backed endpoint.
    Returns one metric with the full list.

    Metric value is a list[dict] (each dict describes one scheduled ICO).
    """
    try:
        data = _post_json(URL, PAYLOAD, timeout=30)
    except requests.HTTPError as e:
        status = getattr(e.response, "status_code", None)
        if status == 429:
            logger.warning("MetaDAO fetch rate-limited (429); skipping this cycle")
            return []
        raise
    except Exception:
        logger.exception("MetaDAO fetch failed; skipping this cycle")
        return []
    scheduled = _extract_scheduled_icos(data)

    return [
        {
            "key": "metadao:icos:scheduled",
            "name": "MetaDAO Scheduled ICOs",
            "value": scheduled,  # list of scheduled ICO dicts
            "unit": "json",
        }
    ]
