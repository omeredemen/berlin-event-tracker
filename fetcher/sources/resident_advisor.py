"""Resident Advisor (ra.co) – club nights, parties, electronic music.
RA has no public API; this uses the GraphQL endpoint the ra.co website itself
calls (unofficial, personal use only, may change without notice).
"""
from __future__ import annotations

import time

from common import categorize, event, parse_iso, window

URL = "https://ra.co/graphql"
SOURCE = "resident_advisor"
HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://ra.co/events/de/berlin",
    "Origin": "https://ra.co",
}
QUERY = """
query GET_EVENT_LISTINGS($filters: FilterInputDtoInput, $page: Int, $pageSize: Int) {
  eventListings(filters: $filters, pageSize: $pageSize, page: $page) {
    data {
      id
      listingDate
      event {
        id date startTime endTime title contentUrl flyerFront isTicketed attending
        venue { id name contentUrl }
        artists { id name }
      }
    }
    totalResults
  }
}
"""


def parse(listings: list[dict]) -> list[dict]:
    out = []
    for item in listings:
        e = item.get("event") or {}
        start = parse_iso(e.get("startTime")) or parse_iso(e.get("date"))
        if not start or not e.get("title"):
            continue
        artists = ", ".join(a.get("name", "") for a in (e.get("artists") or [])[:6])
        venue = (e.get("venue") or {}).get("name", "")
        path = e.get("contentUrl") or f"/events/{e.get('id')}"
        out.append(event(
            source=SOURCE, raw_id=e.get("id"), title=e["title"], start=start,
            end=parse_iso(e.get("endTime")), venue=venue,
            url=f"https://ra.co{path}" if path.startswith("/") else path,
            image=e.get("flyerFront") or "",
            categories=categorize(e["title"], ["nightlife", "music"]),
            description=f"Line-up: {artists}" if artists else "",
            extra={"going": e.get("attending")} if e.get("attending") else None,
        ))
    return out


def fetch(cfg: dict, http) -> list[dict]:
    rcfg = cfg.get("resident_advisor", {})
    area = rcfg.get("area_id", 34)  # 34 = Berlin on ra.co
    start, end = window(min(cfg.get("days_ahead", 30), rcfg.get("days_ahead", 14)))
    listings: list[dict] = []
    for page in range(1, rcfg.get("max_pages", 30) + 1):
        payload = {
            "operationName": "GET_EVENT_LISTINGS",
            "query": QUERY,
            "variables": {
                "filters": {
                    "areas": {"eq": area},
                    "listingDate": {"gte": start.isoformat(), "lte": end.isoformat()},
                },
                "pageSize": 50,
                "page": page,
            },
        }
        r = http.post(URL, json=payload, headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = (r.json().get("data") or {}).get("eventListings") or {}
        batch = data.get("data") or []
        listings.extend(batch)
        if not batch or len(listings) >= (data.get("totalResults") or 0):
            break
        time.sleep(1)
    return parse(listings)
