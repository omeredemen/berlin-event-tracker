"""Calendar (iCal / .ics) feeds – the easiest way to add *anything* you follow:
Meetup groups, Luma community calendars, galleries, venues, Google Calendars.
Add feeds in config.json under "ical_feeds".
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime
from zoneinfo import ZoneInfo

from common import BERLIN, categorize, event, looks_free, to_local, window

SOURCE = "calendar"


def _unfold(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _unescape(v: str) -> str:
    return v.replace("\\n", " ").replace("\\N", " ").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def _parse_dt(value: str, params: dict) -> tuple[datetime | None, bool]:
    v = value.strip()
    try:
        if params.get("VALUE") == "DATE" or len(v) == 8:
            return datetime.combine(date(int(v[:4]), int(v[4:6]), int(v[6:8])), datetime.min.time()), True
        dt = datetime.strptime(v[:15], "%Y%m%dT%H%M%S")
        if v.endswith("Z"):
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        elif "TZID" in params:
            try:
                dt = dt.replace(tzinfo=ZoneInfo(params["TZID"].strip('"')))
            except Exception:
                dt = dt.replace(tzinfo=BERLIN)
        return to_local(dt), False
    except (ValueError, IndexError):
        return None, False


def parse(text: str, feed: dict) -> list[dict]:
    out = []
    current: dict | None = None
    for line in _unfold(text):
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current is not None:
                out.append(current)
            current = None
            continue
        if current is None or ":" not in line:
            continue
        head, value = line.split(":", 1)
        name, *pairs = head.split(";")
        params = dict(p.split("=", 1) for p in pairs if "=" in p)
        current[name.upper()] = (value, params)

    events = []
    hints = feed.get("categories") or []
    label = feed.get("name", "")
    for raw in out:
        if "DTSTART" not in raw:
            continue
        start, all_day = _parse_dt(*raw["DTSTART"])
        end, _ = _parse_dt(*raw["DTEND"]) if "DTEND" in raw else (None, False)
        title = _unescape(raw.get("SUMMARY", ("", {}))[0])
        if not start or not title:
            continue
        if raw.get("STATUS", ("", {}))[0].upper() == "CANCELLED":
            continue
        desc = _unescape(raw.get("DESCRIPTION", ("", {}))[0])
        location = _unescape(raw.get("LOCATION", ("", {}))[0])
        venue, _, address = location.partition(",")
        uid = raw.get("UID", ("", {}))[0] or hashlib.sha1(f"{title}{start}".encode()).hexdigest()
        free = True if feed.get("free") else (True if looks_free(f"{title} {desc}") else None)
        events.append(event(
            source=SOURCE, raw_id=uid, title=title, start=start, end=end, all_day=all_day,
            venue=venue.strip() or feed.get("default_venue", ""), address=address.strip(),
            url=raw.get("URL", ("", {}))[0] or feed.get("link", ""),
            categories=categorize(f"{title} {desc}", hints), free=free,
            description=desc, extra={"feed": label} if label else None,
        ))
    return events


def fetch(cfg: dict, http) -> list[dict]:
    start, end = window(cfg.get("days_ahead", 30))
    out: list[dict] = []
    for feed in cfg.get("ical_feeds", []):
        url = feed.get("url", "")
        if not url or "REPLACE" in url:
            continue
        try:
            r = http.get(url.replace("webcal://", "https://"), timeout=30)
            r.raise_for_status()
            for ev in parse(r.text, feed):
                d = date.fromisoformat(ev["start"][:10])
                e_end = date.fromisoformat(ev["end"][:10]) if ev.get("end") else d
                if e_end >= start and d <= end:
                    out.append(ev)
        except Exception as exc:
            print(f"  [calendar] {feed.get('name', url)} failed: {exc}")
    return out
