"""Luma (luma.com/berlin) – community meetups, networking, socials, tech events.
Uses the public JSON feed the luma.com city page itself loads (unofficial,
no key). Personal use only – it may change without notice.
"""
from __future__ import annotations

import time

from common import categorize, event, parse_iso, window

HOSTS = ["https://api.lu.ma", "https://api2.luma.com"]
PATH = "/discover/get-paginated-events"
SOURCE = "luma"


def parse(entries: list[dict]) -> list[dict]:
    out = []
    for entry in entries:
        e = entry.get("event") or {}
        if e.get("location_type") == "online":
            continue
        start = parse_iso(e.get("start_at"))
        if not start or not e.get("name"):
            continue
        geo = e.get("geo_address_info") or {}
        city = (geo.get("city") or "").lower()
        if city and "berlin" not in city:
            continue
        ticket = entry.get("ticket_info") or {}
        free = ticket.get("is_free") if "is_free" in ticket else None
        price = ""
        if ticket.get("price") and not free:
            p = ticket["price"]
            cents = p.get("cents") if isinstance(p, dict) else None
            if cents:
                price = f"from {cents / 100:.0f} {p.get('currency', 'eur').upper()}"
        host = (entry.get("calendar") or {}).get("name", "")
        slug = e.get("url") or ""
        text = f"{e.get('name')} {host}"
        out.append(event(
            source=SOURCE, raw_id=e.get("api_id") or slug, title=e["name"], start=start,
            end=parse_iso(e.get("end_at")),
            venue=geo.get("address") or geo.get("short_address") or "",
            address=geo.get("full_address") or "",
            url=f"https://luma.com/{slug}" if slug and not slug.startswith("http") else slug,
            image=e.get("cover_url") or "", free=free, price=price,
            categories=categorize(text, ["social"]),
            description=f"Hosted by {host}" if host else "",
            extra={"going": entry.get("guest_count")} if entry.get("guest_count") else None,
        ))
    return out


def fetch(cfg: dict, http) -> list[dict]:
    lcfg = cfg.get("luma", {})
    place_id = lcfg.get("place_id", "discplace-gCfX0s3E9Hgo3rG")
    _, end = window(cfg.get("days_ahead", 30))
    last_error: Exception | None = None
    for host in HOSTS:
        try:
            entries: list[dict] = []
            cursor = None
            for _ in range(lcfg.get("max_pages", 10)):
                params = {"discover_place_api_id": place_id, "pagination_limit": 50}
                if cursor:
                    params["pagination_cursor"] = cursor
                r = http.get(host + PATH, params=params, timeout=30)
                r.raise_for_status()
                data = r.json()
                entries.extend(data.get("entries", []))
                cursor = data.get("next_cursor")
                if not data.get("has_more") or not cursor:
                    break
                # stop once we're past the window
                last_start = parse_iso(((entries[-1] or {}).get("event") or {}).get("start_at"))
                if last_start and last_start.date() > end:
                    break
                time.sleep(1.2)
            return parse(entries)
        except Exception as exc:  # try the next host
            last_error = exc
    raise RuntimeError(f"Luma feed unavailable: {last_error}")
