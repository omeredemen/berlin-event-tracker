"""Write a clearly-labelled SAMPLE docs/events.json so the page can be previewed
before the real fetcher has run. The first real run overwrites it."""
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "fetcher"))
from common import BERLIN, categorize, event  # noqa: E402

random.seed(7)
today = datetime.now(BERLIN).replace(tzinfo=None, minute=0, second=0, microsecond=0)

SAMPLES = [
    ("luma", "Newcomers' Social Night – meet people in Berlin", "Café in Mitte", 19, True, ["social"]),
    ("luma", "Sunday Run Club + Coffee", "Tempelhofer Feld", 10, True, ["social"]),
    ("eventbrite", "Language Exchange & Drinks (DE/EN/ES)", "Bar in Neukölln", 19, True, ["social"]),
    ("calendar", "Board Game Night", "Spielecafé Kreuzberg", 19, True, ["social"]),
    ("eventbrite", "Pub Quiz in English", "Irish pub, Friedrichshain", 20, False, ["social"]),
    ("kulturdaten", "Vernissage: young photography", "Gallery in Wedding", 18, True, ["art"]),
    ("kulturdaten", "Artist talk & guided tour", "Museum in Tiergarten", 15, False, ["talks", "art"]),
    ("ticketmaster", "Indie band – Europe tour", "Concert hall, Friedrichshain", 20, False, ["music"]),
    ("kulturdaten", "Free lunchtime concert", "Philharmonie foyer", 13, True, ["music"]),
    ("resident_advisor", "Club night: techno all night long", "Club in Friedrichshain", 23, False, ["nightlife"]),
    ("eventbrite", "Stand-up comedy in English", "Comedy club, Neukölln", 20, False, ["stage"]),
    ("kulturdaten", "Reading: new Berlin fiction", "Literaturhaus", 19, True, ["talks"]),
    ("luma", "Founders & Friends Afterwork", "Coworking space, Kreuzberg", 18, True, ["social"]),
    ("eventbrite", "Life-drawing session", "Studio, Prenzlauer Berg", 18, False, ["art", "social"]),
]

events = []
for i in range(40):
    src, title, venue, hour, free, hints = SAMPLES[i % len(SAMPLES)]
    start = (today + timedelta(days=i // 3)).replace(hour=hour)
    ev = event(source=src, raw_id=f"sample{i}", title=title, start=start, end=start + timedelta(hours=3),
               venue=venue, url="https://example.org", categories=categorize(title, hints),
               free=free if free else None, price="" if free else "from 12 EUR",
               description="Sample event for previewing the layout.")
    events.append(ev)
for j, (title, weeks) in enumerate([("Exhibition: Berlin photography 1990–2000", 6), ("Group show: textile art", 3)]):
    s = today - timedelta(days=10)
    events.append(event(source="kulturdaten", raw_id=f"ongoing{j}", title=title, start=s.replace(hour=0),
                        end=s + timedelta(weeks=weeks), all_day=True, venue="Museum, Mitte",
                        url="https://example.org", categories=["art"], free=j == 1, description="Sample long-running exhibition."))
events.sort(key=lambda e: e["start"])
(ROOT / "docs" / "events.json").write_text(json.dumps({
    "sample": True, "updated": datetime.now(BERLIN).isoformat(timespec="minutes"),
    "sources": {k: {"ok": True, "count": sum(e["source"] == k for e in events)}
                for k in ["calendar", "luma", "kulturdaten", "ticketmaster", "resident_advisor", "eventbrite"]},
    "events": events}, ensure_ascii=False, indent=1))
print(f"wrote {len(events)} sample events")
