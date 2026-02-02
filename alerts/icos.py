from datetime import datetime, timezone
from typing import Dict, List, Optional

from db.repo import ico_alert_state, mark_ico_released, mark_ico_scheduled


def _utc_today() -> datetime.date:
    return datetime.now(timezone.utc).date()


def _parse_iso_date(iso_str: str) -> Optional[datetime.date]:
    """
    Parse ISO-ish strings (handles trailing 'Z') into a UTC date.
    Returns None on failure.
    """
    try:
        clean = iso_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean).astimezone(timezone.utc).date()
    except Exception:
        return None


def _pretty_date(iso_str: Optional[str]) -> Optional[str]:
    if not iso_str:
        return None
    try:
        clean = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean).astimezone(timezone.utc)
        return dt.strftime("%b %d, %Y (%H:%M UTC)")
    except Exception:
        return iso_str


def handle_ico_schedule(entries: List[Dict]) -> List[Dict]:
    """
    entries: list of ICO dicts from adapters.gov.metadao.fetch()
    Emits:
      - major alert when a new scheduled ICO is first seen
      - major alert on the day of launch (UTC) if not already sent
    """
    alerts: List[Dict] = []
    today = _utc_today()

    for ico in entries:
        block_id = ico.get("block_id") or ico.get("project")
        if not block_id:
            continue

        project = ico.get("project", "Unknown project")
        start_iso = ico.get("start_date")
        start_date = _parse_iso_date(start_iso) if start_iso else None
        start_pretty = _pretty_date(start_iso) if start_iso else None
        tldr = ico.get("tldr")
        fundraising_goals = ico.get("fundraising_goals")
        twitter = ico.get("twitter_link")

        state = ico_alert_state(block_id)

        # New scheduled ICO
        if state["scheduled"] is None:
            msg = (
                f":heart_eyes_cat: {project} ICO scheduled for "
                + (f"{start_pretty}" if start_pretty else "")
                + (f"\n\n{tldr}" if tldr else "")
                + (f"\n{fundraising_goals}" if fundraising_goals else "")
                + (f"\nLink: {twitter}" if twitter else "")
            )
            alerts.append(
                {
                    "category": "icos",
                    "level": "major",
                    "metric_key": "metadao:icos:scheduled",
                    "message": msg,
                }
            )
            mark_ico_scheduled(block_id)

        # Launch day alert
        if start_date and start_date == today and state["released"] is None:
            msg = (
                f":smile_cat: {project} ICO launches today!"
            )
            alerts.append(
                {
                    "category": "icos",
                    "level": "major",
                    "metric_key": "metadao:icos:scheduled",
                    "message": msg,
                }
            )
            mark_ico_released(block_id)

    return alerts
