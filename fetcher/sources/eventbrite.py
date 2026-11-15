"""Eventbrite – socials, networking, workshops, free events.
Eventbrite removed public event search from its API in 2019/2020, so this reads
the structured data (schema.org JSON-LD) embedded in its public Berlin search
pages. Unofficial, personal use only, may change without notice.
"""
from __future__ import annotations

import json
import re
import time

from common import categorize, event, looks_free, parse_iso

SOURCE = "eventbrite"
BASE = "https://www.eventbrite.de/d/germany--berlin/{slug}/"

# Which search pages to read, and the category hint each one implies.
DEFAULT_PAGES = {
    "free--events": [],
    "networking": ["social"],
    "social-activities--events": ["social"],
    "arts--events": ["art"],
    "music--events": ["music"],
}

SERVER_DATA_RE = re.compile(r"window\.__SERVER_DATA__\s*=\s*")
LD_RE = re.compile(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.S | re.I)


def _iter_ld_events(html: str):
    for block in LD_RE.findall(html):
        try:
            data = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
                continue
            if not isinstance(node, dict):
                continue
            typ = node.get("@type")
            types = typ if isinstance(typ, list) else [typ]
            if any(t and str(t).endswith("Event") for t in types):
                yield node
            for key in ("itemListElement", "item", "@graph"):
                if key in node:
                    stack.append(node[key])


def _event_times(html: str) -> dict[str, tuple[str | None, str | None]]:
    """Event id → (start, end) as ISO strings with times.

    The JSON-LD only has dates; the page's own __SERVER_DATA__ blob has
    start_date/start_time, so we read times from there.
    """
    m = SERVER_DATA_RE.search(html)
    if not m:
        return {}
    try:
        data, _ = json.JSONDecoder().raw_decode(html, m.end())
    except json.JSONDecodeError:
        return {}
    times: dict[str, tuple[str | None, str | None]] = {}
    stack = [data]
    while stack:
        node = stack.pop()
        if isinstance(node, list):
            stack.extend(node)
        elif isinstance(node, dict):
            eid = str(node.get("eid") or node.get("id") or "")
            if eid and node.get("start_date") and node.get("start_time"):
                start = f"{node['start_date']}T{node['start_time']}"
                end = f"{node['end_date']}T{node.get('end_time') or '00:00'}" if node.get("end_date") else None
                times[eid] = (start, end)
            stack.extend(node.values())
    return times


def parse(html: str, hints: list[str], free_page: bool = False) -> list[dict]:
    times = _event_times(html)
    out = []
    for e in _iter_ld_events(html):
        name = e.get("name") or ""
        url = e.get("url") or ""
        raw_id = re.search(r"(\d{8,})", url)
        start_s, end_s = times.get(raw_id.group(1) if raw_id else "", (e.get("startDate"), e.get("endDate")))
        start = parse_iso(start_s)
        if not name or not start:
            continue
        loc = e.get("location") or {}
        if isinstance(loc, list):
            loc = loc[0] if loc else {}
        if loc.get("@type") == "VirtualLocation":
            continue
        addr = loc.get("address") or {}
        if isinstance(addr, dict):
            locality = addr.get("addressLocality") or ""
            if locality and "berlin" not in locality.lower():
                continue
            address = ", ".join(x for x in [addr.get("streetAddress"), addr.get("postalCode")] if x)
        else:
            address = str(addr)
        offers = e.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        low = offers.get("lowPrice", offers.get("price"))
        free = True if free_page else None
        price = ""
        try:
            if low is not None:
                free = float(low) == 0
                if not free:
                    price = f"from {float(low):.0f} {offers.get('priceCurrency', 'EUR')}"
        except (TypeError, ValueError):
            pass
        desc = e.get("description") or ""
        if free is None and looks_free(f"{name} {desc}"):
            free = True
        image = e.get("image") or ""
        if isinstance(image, list):
            image = image[0] if image else ""
        out.append(event(
            source=SOURCE, raw_id=raw_id.group(1) if raw_id else url, title=name, start=start,
            all_day=len(start_s or "") <= 10,
            end=parse_iso(end_s), venue=loc.get("name", ""), address=address,
            url=url.split("?")[0], image=image if isinstance(image, str) else "",
            categories=categorize(f"{name} {desc}", hints), free=free, price=price,
            description=desc,
        ))
    return out


def fetch(cfg: dict, http) -> list[dict]:
    ecfg = cfg.get("eventbrite", {})
    pages = ecfg.get("pages") or DEFAULT_PAGES
    out: list[dict] = []
    for slug, hints in pages.items():
        for n in range(1, ecfg.get("pages_per_search", 3) + 1):
            r = http.get(BASE.format(slug=slug), params={"page": n}, timeout=30)
            if r.status_code == 404:
                break
            r.raise_for_status()
            batch = parse(r.text, hints, free_page=slug.startswith("free"))
            out.extend(batch)
            if not batch:
                break
            time.sleep(1.5)
    return out
