"""Ticketmaster Discovery API – concerts, shows, comedy, sports.
Official API, free key: https://developer.ticketmaster.com (5,000 calls/day).
Set the key in the TICKETMASTER_API_KEY environment variable / GitHub secret.
"""
from __future__ import annotations

import os

from common import categorize, event, parse_iso, window

URL = "https://app.ticketmaster.com/discovery/v2/events.json"
SOURCE = "ticketmaster"

SEGMENT_HINTS = {
    "Music": ["music"],
    "Arts & Theatre": ["stage"],
    "Film": ["talks"],
}


def _best_image(images: list[dict]) -> str:
    imgs = [i for i in images or [] if i.get("ratio") == "16_9"] or images or []
    imgs.sort(key=lambda i: abs((i.get("width") or 0) - 640))
    return imgs[0]["url"] if imgs else ""


def parse(payload: dict) -> list[dict]:
    out = []
    for e in (payload.get("_embedded") or {}).get("events", []):
        dates = (e.get("dates") or {}).get("start") or {}
        if (e.get("dates") or {}).get("status", {}).get("code") in ("cancelled", "postponed"):
            continue
        start = parse_iso(dates.get("dateTime")) or parse_iso(
            f"{dates.get('localDate')}T{dates.get('localTime') or '00:00:00'}" if dates.get("localDate") else None
        )
        if not start:
            continue
        cls = (e.get("classifications") or [{}])[0]
        segment = (cls.get("segment") or {}).get("name", "")
        if segment == "Sports":
            continue  # not what we're after
        genre = (cls.get("genre") or {}).get("name", "")
        venue_obj = ((e.get("_embedded") or {}).get("venues") or [{}])[0]
        addr = (venue_obj.get("address") or {}).get("line1", "")
        prices = e.get("priceRanges") or []
        price = ""
        if prices:
            p = prices[0]
            if p.get("min") is not None:
                price = f"from {p['min']:.0f} {p.get('currency', 'EUR')}"
        text = f"{e.get('name', '')} {segment} {genre} {e.get('info', '')}"
        out.append(event(
            source=SOURCE, raw_id=e.get("id"), title=e.get("name", ""), start=start,
            all_day=bool(dates.get("dateTBA") or dates.get("timeTBA") or not dates.get("localTime")),
            venue=venue_obj.get("name", ""), address=addr, url=e.get("url", ""),
            image=_best_image(e.get("images")), price=price,
            categories=categorize(text, SEGMENT_HINTS.get(segment)),
            free=False if prices else None,
            description=e.get("info") or e.get("pleaseNote") or "",
            extra={"genre": genre} if genre and genre != "Undefined" else None,
        ))
    return out


def fetch(cfg: dict, http) -> list[dict]:
    key = os.environ.get("TICKETMASTER_API_KEY")
    if not key:
        print("  [ticketmaster] no TICKETMASTER_API_KEY set – skipping")
        return []
    start, end = window(cfg.get("days_ahead", 30))
    out: list[dict] = []
    # Deep paging is capped at 1,000 results (size * page < 1000).
    for page in range(5):
        r = http.get(URL, params={
            "apikey": key, "city": "Berlin", "countryCode": "DE", "locale": "*",
            "startDateTime": f"{start.isoformat()}T00:00:00Z",
            "endDateTime": f"{end.isoformat()}T23:59:59Z",
            "size": 199, "page": page, "sort": "date,asc",
        }, timeout=30)
        r.raise_for_status()
        data = r.json()
        out.extend(parse(data))
        info = data.get("page") or {}
        if page + 1 >= info.get("totalPages", 0):
            break
    return out
