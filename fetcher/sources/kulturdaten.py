"""kulturdaten.berlin – Berlin's open culture database (museums, exhibitions,
readings, concerts, district events). Official, free, no key needed.
Docs: https://kulturdaten.readme.io  ·  Spec: github.com/technologiestiftung/kulturdaten-api
"""
from __future__ import annotations

from datetime import datetime

from common import categorize, event, window

BASE = "https://api-v2.kulturdaten.berlin/api"
SOURCE = "kulturdaten"
PAGE_SIZE = 500  # API maximum

# Events themselves carry only a title; the linked "attraction" has category tags.
TAG_CATEGORIES = {
    "Music": "music", "Festivals": "music",
    "Exhibitions": "art", "Art": "art",
    "Stages": "stage", "Dance": "stage",
    "Lectures": "talks", "Conferences": "talks", "InformationEvents": "talks",
    "Walks": "talks", "Politics": "talks",
    "Recreation": "social", "ChristmasTime": "social",
}
# Events whose tags are *only* from this list are skipped (consultation hours,
# homework help, police prevention talks, …). Override with kulturdaten.skip_tags.
DEFAULT_SKIP_TAGS = ["Police", "Children", "Health", "Seniors", "Education", "WeeklyMarkets"]


def _label(obj: dict | None, lang: str = "en") -> str:
    """Multilingual {'de': ..., 'en': ...} → string, preferring `lang`."""
    if not obj:
        return ""
    return obj.get(lang) or obj.get("de") or next(iter(obj.values()), "")


def _paged(http, path: str, params: dict, key: str, max_pages: int = 40) -> list[dict]:
    items: list[dict] = []
    for page in range(1, max_pages + 1):
        r = http.get(f"{BASE}{path}", params={**params, "page": page, "pageSize": PAGE_SIZE}, timeout=60)
        r.raise_for_status()
        data = r.json().get("data", {})
        batch = data.get(key, [])
        items.extend(batch)
        total = data.get("totalCount", 0)
        if not batch or len(items) >= total:
            break
    return items


def _tag_names(attraction: dict) -> list[str]:
    return [t.rsplit(".", 1)[-1] for t in attraction.get("tags") or []]


def _dt(d: str | None, t: str | None) -> datetime | None:
    if not d:
        return None
    t = (t or "00:00")[:5]
    try:
        return datetime.fromisoformat(f"{d}T{t}")
    except ValueError:
        return None


def parse(events: list[dict], locations: dict[str, dict],
          attractions: dict[str, dict] | None = None,
          skip_tags: list[str] | None = None) -> list[dict]:
    attractions = attractions or {}
    skip = set(DEFAULT_SKIP_TAGS if skip_tags is None else skip_tags)
    out = []
    for e in events:
        if e.get("status") not in (None, "event.published"):
            continue
        if e.get("scheduleStatus") in ("event.cancelled", "event.postponed"):
            continue
        sched = e.get("schedule") or {}
        # The API uses 00:00:00 for "no time given".
        start_time = (sched.get("startTime") or "")[:5]
        if start_time == "00:00" and (sched.get("endTime") or "00:00")[:5] == "00:00":
            sched = {**sched, "startTime": None, "endTime": None}
        start = _dt(sched.get("startDate"), sched.get("startTime"))
        end = _dt(sched.get("endDate") or sched.get("startDate"), sched.get("endTime"))
        attractions_refs = e.get("attractions") or []
        title = _label(e.get("title")) or (attractions_refs and _label(attractions_refs[0].get("referenceLabel"))) or ""
        if not title or not start:
            continue

        attraction = attractions.get(attractions_refs[0].get("referenceId"), {}) if attractions_refs else {}
        tags = _tag_names(attraction)
        if tags and all(t in skip for t in tags):
            continue

        locs = e.get("locations") or []
        venue, address, borough = "", "", ""
        if locs:
            ref = locs[0]
            loc = locations.get(ref.get("referenceId"), {})
            venue = _label(loc.get("title")) or _label(ref.get("referenceLabel"))
            a = loc.get("address") or {}
            address = ", ".join(x for x in [a.get("streetAddress"), a.get("postalCode")] if x)
            borough = loc.get("borough") or ""

        admission = e.get("admission") or {}
        ticket_type = admission.get("ticketType")
        free = True if ticket_type == "ticketType.freeOfCharge" else (False if ticket_type else None)

        desc = _label(e.get("description")) or _label(attraction.get("description"))
        hints = list(dict.fromkeys(TAG_CATEGORIES[t] for t in tags if t in TAG_CATEGORIES))
        cats = categorize(f"{title} {desc} {venue}", hints)

        out.append(event(
            source=SOURCE, raw_id=e.get("identifier"), title=title, start=start, end=end,
            all_day=not sched.get("startTime"), venue=venue, address=address,
            url=e.get("website") or admission.get("admissionLink") or "",
            categories=cats, free=free, description=desc,
            extra={"area": borough} if borough else None,
        ))
    return out


def fetch(cfg: dict, http) -> list[dict]:
    start, end = window(cfg.get("days_ahead", 30))
    events = _paged(http, "/events", {"startDate": start.isoformat(), "endDate": end.isoformat()}, "events")
    try:
        locs = _paged(http, "/locations", {}, "locations")
        loc_map = {l.get("identifier"): l for l in locs}
    except Exception as exc:  # addresses are nice-to-have
        print(f"  [kulturdaten] could not load locations: {exc}")
        loc_map = {}
    try:
        attrs = _paged(http, "/attractions", {}, "attractions", max_pages=100)
        attr_map = {a.get("identifier"): a for a in attrs}
    except Exception as exc:  # without tags we fall back to keyword matching
        print(f"  [kulturdaten] could not load attractions: {exc}")
        attr_map = {}
    skip = (cfg.get("kulturdaten") or {}).get("skip_tags")
    return parse(events, loc_map, attr_map, skip)
