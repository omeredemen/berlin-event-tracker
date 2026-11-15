"""Fetch Berlin events from every enabled source and write docs/events.json.

    python fetcher/fetch_events.py            # uses config.json
    python fetcher/fetch_events.py --only luma kulturdaten

If a source fails, its events from the previous run are kept (as long as they
are still upcoming), so one broken site never empties your list.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import BERLIN, dedupe_key, session, window  # noqa: E402
from sources import eventbrite, ical_feeds, kulturdaten, luma, resident_advisor, ticketmaster  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "events.json"

# Order = priority when the same event appears in several sources.
SOURCES = {
    "calendar": ical_feeds,
    "luma": luma,
    "kulturdaten": kulturdaten,
    "ticketmaster": ticketmaster,
    "resident_advisor": resident_advisor,
    "eventbrite": eventbrite,
}


def in_window(ev: dict, start: date, end: date) -> bool:
    if not ev.get("start"):
        return False
    s = date.fromisoformat(ev["start"][:10])
    e = date.fromisoformat(ev["end"][:10]) if ev.get("end") else s
    if e < s:
        e = s
    return e >= start and s <= end


def merge(groups: list[list[dict]]) -> list[dict]:
    seen: dict[str, dict] = {}
    for group in groups:
        for ev in group:
            key = dedupe_key(ev["title"], ev["start"])
            if key in seen:
                kept = seen[key]
                kept.setdefault("alsoOn", []).append({"source": ev["source"], "url": ev["url"]})
                for field in ("image", "venue", "address", "description", "price"):
                    if not kept.get(field) and ev.get(field):
                        kept[field] = ev[field]
                if kept.get("free") is None and ev.get("free") is not None:
                    kept["free"] = ev["free"]
                kept["categories"] = list(dict.fromkeys(kept["categories"] + ev["categories"]))
                if "other" in kept["categories"] and len(kept["categories"]) > 1:
                    kept["categories"].remove("other")
                continue
            seen[key] = ev
    return list(seen.values())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config.json"))
    ap.add_argument("--only", nargs="*", help="only run these sources")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    start, end = window(cfg.get("days_ahead", 30))
    previous = json.loads(OUT.read_text()) if OUT.exists() else {"events": []}
    if previous.get("sample"):
        previous = {"events": []}  # never carry the preview data forward
    http = session()

    groups, status = [], {}
    for name, module in SOURCES.items():
        enabled = cfg.get("sources", {}).get(name, True)
        if args.only and name not in args.only:
            enabled = False
        if not enabled:
            continue
        t0 = time.time()
        print(f"→ {name}")
        try:
            events = [e for e in module.fetch(cfg, http) if in_window(e, start, end)]
            status[name] = {"ok": True, "count": len(events)}
            print(f"  {len(events)} events ({time.time() - t0:.1f}s)")
            if not events:
                # Zero results usually means the site changed, not an empty city.
                old = [e for e in previous["events"] if e.get("source") == name and in_window(e, start, end)]
                if old:
                    events = old
                    status[name] = {"ok": False, "count": len(old), "error": "returned 0 events – kept last run"}
        except Exception as exc:
            events = [e for e in previous["events"] if e.get("source") == name and in_window(e, start, end)]
            status[name] = {"ok": False, "count": len(events), "error": str(exc)[:200]}
            print(f"  FAILED: {exc} – kept {len(events)} from last run")
        groups.append(events)

    merged = merge(groups)
    merged.sort(key=lambda e: (e["start"], e["title"].lower()))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "updated": datetime.now(BERLIN).isoformat(timespec="minutes"),
        "window": {"from": start.isoformat(), "to": end.isoformat()},
        "sources": status,
        "events": merged,
    }, ensure_ascii=False, indent=1))
    print(f"\nWrote {len(merged)} events to {OUT.relative_to(ROOT)}")
    return 0 if any(s["ok"] for s in status.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
