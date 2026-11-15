"""Offline tests: feed each parser a payload shaped like the real API response.

    python -m pytest tests  (or: python tests/test_parsers.py)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "fetcher"))

from common import categorize  # noqa: E402
from fetch_events import merge  # noqa: E402
from sources import eventbrite, ical_feeds, kulturdaten, luma, resident_advisor, ticketmaster  # noqa: E402


def test_kulturdaten():
    events = [{
        "type": "type.Event", "identifier": "E1", "status": "event.published",
        "scheduleStatus": "event.scheduled",
        "schedule": {"startDate": "2026-11-20", "startTime": "18:00:00", "endDate": "2026-11-20", "endTime": "21:00"},
        "attractions": [{"referenceType": "type.Attraction", "referenceId": "A1",
                         "referenceLabel": {"de": "Vernissage: Neue Malerei", "en": "Opening: New Painting"}}],
        "locations": [{"referenceType": "type.Location", "referenceId": "L1", "referenceLabel": {"de": "Galerie Nord"}}],
        "admission": {"ticketType": "ticketType.freeOfCharge"},
        "website": "https://example.org/e1",
    }, {
        "type": "type.Event", "identifier": "E2", "status": "event.published",
        "scheduleStatus": "event.cancelled",
        "schedule": {"startDate": "2026-11-21", "startTime": "18:00:00"},
        "attractions": [{"referenceType": "type.Attraction", "referenceId": "A2", "referenceLabel": {"de": "Abgesagt"}}],
    }]
    locs = {"L1": {"identifier": "L1", "title": {"de": "Galerie Nord | Kunstverein Tiergarten"},
                   "address": {"streetAddress": "Turmstraße 75", "postalCode": "10551"}, "borough": "Mitte"}}
    out = kulturdaten.parse(events, locs)
    assert len(out) == 1
    e = out[0]
    assert e["title"] == "Opening: New Painting"
    assert e["start"] == "2026-11-20T18:00" and e["end"] == "2026-11-20T21:00"
    assert e["free"] is True and "art" in e["categories"]
    assert e["address"] == "Turmstraße 75, 10551" and e["area"] == "Mitte"


def test_kulturdaten_attraction_tags():
    def ev(eid, aid, title):
        return {"type": "type.Event", "identifier": eid, "status": "event.published",
                "scheduleStatus": "event.scheduled",
                "schedule": {"startDate": "2026-11-20", "endDate": "2026-11-20",
                             "startTime": "00:00:00", "endTime": "00:00:00"},
                "attractions": [{"referenceId": aid, "referenceLabel": {"de": title}}]}
    events = [ev("E1", "A1", "Country-Linedance im STZ"),
              ev("E2", "A2", "Hausaufgabenhilfe für die 1.-6. Klasse"),
              ev("E3", "A3", "Hochzeiten aus den Familienalben")]
    attrs = {
        "A1": {"tags": ["attraction.category.Music", "attraction.category.Recreation"]},
        "A2": {"tags": ["attraction.category.Children", "attraction.category.Education"]},
        "A3": {"tags": ["attraction.category.Exhibitions"], "description": {"de": "Fotos aus Familienalben"}},
    }
    out = {e["id"]: e for e in kulturdaten.parse(events, {}, attrs)}
    assert set(out) == {"kulturdaten:E1", "kulturdaten:E3"}  # homework help skipped
    assert out["kulturdaten:E1"]["categories"][:2] == ["music", "social"]
    assert out["kulturdaten:E3"]["categories"][0] == "art"
    assert out["kulturdaten:E3"]["description"] == "Fotos aus Familienalben"
    # 00:00–00:00 means "no time given" → all-day
    assert out["kulturdaten:E1"]["allDay"] is True
    # skip list can be turned off
    assert len(kulturdaten.parse(events, {}, attrs, skip_tags=[])) == 3


def test_ticketmaster():
    payload = {"_embedded": {"events": [{
        "id": "TM1", "name": "Sigur Rós", "url": "https://www.ticketmaster.de/event/1",
        "dates": {"start": {"localDate": "2026-11-25", "localTime": "20:00:00", "dateTime": "2026-11-25T19:00:00Z"},
                  "status": {"code": "onsale"}},
        "classifications": [{"segment": {"name": "Music"}, "genre": {"name": "Rock"}}],
        "images": [{"ratio": "16_9", "width": 640, "url": "https://img/1.jpg"}],
        "priceRanges": [{"min": 59.5, "currency": "EUR"}],
        "_embedded": {"venues": [{"name": "Uber Eats Music Hall", "address": {"line1": "Uber-Platz 2"}}]},
    }, {
        "id": "TM2", "name": "Eisbären vs X", "dates": {"start": {"localDate": "2026-11-26"}},
        "classifications": [{"segment": {"name": "Sports"}}],
    }]}, "page": {"totalPages": 1}}
    out = ticketmaster.parse(payload)
    assert len(out) == 1
    assert out[0]["start"] == "2026-11-25T20:00"  # UTC → Berlin
    assert "music" in out[0]["categories"] and out[0]["price"] == "from 60 EUR"


def test_luma():
    entries = [{
        "event": {"api_id": "evt-1", "name": "Berlin Newcomers Social Night", "url": "abc123",
                  "start_at": "2026-11-18T18:30:00.000Z", "end_at": "2026-11-18T21:00:00.000Z",
                  "location_type": "offline", "cover_url": "https://img/l.jpg",
                  "geo_address_info": {"city": "Berlin", "address": "Café Mitte", "full_address": "Torstr. 1, Berlin"}},
        "calendar": {"name": "Berlin Socials"}, "ticket_info": {"is_free": True}, "guest_count": 42,
    }, {
        "event": {"api_id": "evt-2", "name": "Online webinar", "url": "x", "start_at": "2026-11-18T18:30:00Z",
                  "location_type": "online"},
    }]
    out = luma.parse(entries)
    assert len(out) == 1
    e = out[0]
    assert e["url"] == "https://luma.com/abc123" and e["start"] == "2026-11-18T19:30"
    assert e["free"] is True and e["categories"][0] == "social" and e["going"] == 42


def test_resident_advisor():
    listings = [{"id": "L1", "listingDate": "2026-11-21T00:00:00.000", "event": {
        "id": "2550001", "date": "2026-11-21T00:00:00.000", "startTime": "2026-11-21T23:00:00.000",
        "endTime": "2026-11-22T08:00:00.000", "title": "Klubnacht", "contentUrl": "/events/2550001",
        "flyerFront": "https://images.ra.co/x.jpg", "attending": 900,
        "venue": {"name": "Berghain"}, "artists": [{"name": "A"}, {"name": "B"}]}}]
    out = resident_advisor.parse(listings)
    assert out[0]["url"] == "https://ra.co/events/2550001"
    assert out[0]["start"] == "2026-11-21T23:00" and "nightlife" in out[0]["categories"]


def test_eventbrite():
    ld = {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "item": {
            "@type": "Event", "name": "Language Exchange & Drinks",
            "startDate": "2026-11-19T19:00:00+01:00", "endDate": "2026-11-19T22:00:00+01:00",
            "url": "https://www.eventbrite.de/e/language-exchange-tickets-1234567890?aff=x",
            "location": {"@type": "Place", "name": "Bar X",
                         "address": {"streetAddress": "Weserstr. 5", "addressLocality": "Berlin", "postalCode": "12047"}},
            "offers": {"@type": "AggregateOffer", "lowPrice": "0", "priceCurrency": "EUR"}}},
        {"@type": "ListItem", "position": 2, "item": {
            "@type": "Event", "name": "Online thing", "startDate": "2026-11-19T19:00:00+01:00",
            "location": {"@type": "VirtualLocation"}}},
    ]}
    html = f'<html><script type="application/ld+json">{json.dumps(ld)}</script></html>'
    out = eventbrite.parse(html, ["social"])
    assert len(out) == 1
    e = out[0]
    assert e["free"] is True and e["id"] == "eventbrite:1234567890"
    assert e["url"].endswith("1234567890") and e["categories"][0] == "social"


def test_eventbrite_times_from_server_data():
    # Real search pages: JSON-LD has dates only, __SERVER_DATA__ has the times.
    ld = {"@type": "ItemList", "itemListElement": [{"@type": "ListItem", "item": {
        "@type": "Event", "name": "LGBTIQ+ After Work", "startDate": "2026-11-24", "endDate": "2026-11-24",
        "url": "https://www.eventbrite.co.uk/e/after-work-berlin-tickets-1980552030438",
        "location": {"@type": "Place", "name": "Bar", "address": {"addressLocality": "Berlin"}}}},
        {"@type": "ListItem", "item": {
        "@type": "Event", "name": "No time known", "startDate": "2026-11-25",
        "url": "https://www.eventbrite.de/e/x-tickets-5555555555",
        "location": {"@type": "Place", "name": "Bar", "address": {"addressLocality": "Berlin"}}}}]}
    server = {"search_data": {"events": {"results": [{
        "id": "1980552030438", "eid": "1980552030438", "name": "LGBTIQ+ After Work",
        "start_date": "2026-11-24", "start_time": "18:00", "end_date": "2026-11-24", "end_time": "22:00"}]}}}
    html = (f'<script type="application/ld+json">{json.dumps(ld)}</script>'
            f'<script>window.__SERVER_DATA__ = {json.dumps(server)};</script>')
    out = {e["title"]: e for e in eventbrite.parse(html, [])}
    e = out["LGBTIQ+ After Work"]
    assert e["start"] == "2026-11-24T18:00" and e["end"] == "2026-11-24T22:00" and e["allDay"] is False
    assert out["No time known"]["allDay"] is True


def test_ical():
    ics = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
        "BEGIN:VEVENT\r\nUID:m1@meetup.com\r\nSUMMARY:Board Game Night\\, Kreuzberg\r\n"
        "DTSTART;TZID=Europe/Berlin:20261120T190000\r\nDTEND;TZID=Europe/Berlin:20261120T220000\r\n"
        "LOCATION:Spielwiese\\, Kottbusser Damm 1\\, Berlin\r\nURL:https://www.meetup.com/x/events/1/\r\n"
        "DESCRIPTION:Free entry\\, bring friends! This is a long line that gets\r\n  folded.\r\nEND:VEVENT\r\n"
        "BEGIN:VEVENT\r\nUID:x2\r\nSUMMARY:All-day show\r\nDTSTART;VALUE=DATE:20261122\r\nEND:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    out = ical_feeds.parse(ics, {"name": "Board gamers", "categories": ["social"]})
    assert len(out) == 2
    a, b = out
    assert a["title"] == "Board Game Night, Kreuzberg" and a["start"] == "2026-11-20T19:00"
    assert a["venue"] == "Spielwiese" and a["free"] is True
    assert b["allDay"] is True and b["start"] == "2026-11-22T00:00"


def test_merge_dedupes():
    a = {"id": "luma:1", "source": "luma", "title": "Jazz Night!", "start": "2026-11-20T20:00", "url": "u1",
         "categories": ["social"], "free": None, "image": ""}
    b = {"id": "eventbrite:2", "source": "eventbrite", "title": "jazz night", "start": "2026-11-20T21:00", "url": "u2",
         "categories": ["music"], "free": True, "image": "img"}
    out = merge([[a], [b]])
    assert len(out) == 1 and out[0]["free"] is True and out[0]["image"] == "img"
    assert set(out[0]["categories"]) == {"social", "music"} and out[0]["alsoOn"][0]["source"] == "eventbrite"


def test_categorize():
    assert "art" in categorize("Vernissage in der Galerie")
    assert "music" in categorize("Jazz concert at A-Trane")
    assert categorize("Something unrelated") == ["other"]
    assert "art" not in categorize("Startup breakfast")  # 'start' must not match 'art'


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
