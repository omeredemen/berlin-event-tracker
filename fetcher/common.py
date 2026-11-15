"""Shared helpers: HTTP session, time handling, categorisation."""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

BERLIN = ZoneInfo("Europe/Berlin")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en,de;q=0.8"})
    return s


# ---------------------------------------------------------------- time helpers

def to_local(dt: datetime) -> datetime:
    """Return a naive datetime in Berlin local time."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(BERLIN).replace(tzinfo=None)


def parse_iso(value: str | None) -> datetime | None:
    """Parse ISO-ish strings ('2026-11-20T19:00:00Z', '...+01:00', '2026-11-20')."""
    if not value:
        return None
    v = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        try:
            dt = datetime.combine(date.fromisoformat(v[:10]), datetime.min.time())
        except ValueError:
            return None
    return to_local(dt)


def fmt(dt: datetime | None) -> str | None:
    return dt.strftime("%Y-%m-%dT%H:%M") if dt else None


def today_local() -> date:
    return datetime.now(BERLIN).date()


def window(days_ahead: int) -> tuple[date, date]:
    start = today_local()
    return start, start + timedelta(days=days_ahead)


# --------------------------------------------------------------- categorising

CATEGORIES = ["social", "art", "music", "nightlife", "talks", "stage", "other"]

# Order matters: first matching rule wins for the *primary* category, but an
# event can collect several categories.
KEYWORDS: dict[str, list[str]] = {
    "social": [
        "meetup", "meet-up", "meet up", "networking", "stammtisch", "social",
        "mixer", "language exchange", "sprachcafé", "sprachcafe", "tandem",
        "community", "newcomers", "expat", "international", "make friends",
        "board game", "brettspiel", "quiz", "pub quiz", "run club", "running club",
        "picnic", "speed friending", "singles", "dinner", "brunch", "coworking",
        "hangout", "get-together", "get together", "afterwork", "after work",
        "walk & talk", "volunteer", "potluck", "karaoke",
    ],
    "art": [
        "exhibition", "ausstellung", "gallery", "galerie", "vernissage",
        "finissage", "opening", "eröffnung", "museum", "kunst", " art ",
        " arts ", "artist talk", "painting", "malerei", "photograph", "fotografie",
        "sculpture", "installation", "biennale", "gallery weekend", "collection",
        "sammlung", "werkschau", "retrospective", "retrospektive",
    ],
    "music": [
        "concert", "konzert", "live music", "livemusik", "band", "jazz",
        "orchestra", "orchester", "philharmon", "choir", "chor", "recital",
        "gig", "unplugged", "singer", "songwriter", "quartet",
        "quartett", "symphon", "sinfonie", "opera", "oper", "festival",
    ],
    "nightlife": [
        "party", "club night", "rave", "techno", "house music", " dj", "dj ",
        "open air", "afterhour", "disco", "tanz", "dance night",
    ],
    "talks": [
        "talk", "lecture", "vortrag", "reading", "lesung", "workshop", "panel",
        "discussion", "diskussion", "führung", "guided tour", "tour through",
        "seminar", "course", "kurs", "book launch", "podium", "film screening",
        "screening", "filmvorführung", "hackathon", "conference",
    ],
    "stage": [
        "theater", "theatre", "comedy", "stand-up", "standup", "kabarett",
        "cabaret", "musical", "ballet", "ballett", "performance", "dance theatre",
        "tanztheater", "varieté", "variete", "improv", "show", "zirkus", "circus",
    ],
}


def categorize(text: str, hints: list[str] | None = None) -> list[str]:
    """Return categories for an event from its text plus source-provided hints."""
    t = f" {text.lower()} "
    cats: list[str] = list(dict.fromkeys(hints or []))
    for cat, words in KEYWORDS.items():
        if cat in cats:
            continue
        if any(w in t for w in words):
            cats.append(cat)
    return cats or ["other"]


FREE_WORDS = ["free entry", "free admission", "eintritt frei", "freier eintritt",
              "kostenlos", "gratis", "free event", "eintritt: frei"]


def looks_free(text: str) -> bool:
    t = text.lower()
    return any(w in t for w in FREE_WORDS)


# ------------------------------------------------------------------- misc

def clean(text: str | None, limit: int | None = None) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if limit and len(text) > limit:
        text = text[: limit - 1].rsplit(" ", 1)[0] + "…"
    return text


def make_id(source: str, raw_id: str) -> str:
    return f"{source}:{raw_id}"


def dedupe_key(title: str, start: str | None) -> str:
    norm = re.sub(r"[^a-z0-9äöüß]", "", title.lower())[:40]
    day = (start or "")[:10]
    return hashlib.sha1(f"{norm}|{day}".encode()).hexdigest()[:16]


def event(
    *, source: str, raw_id: str, title: str, start: datetime | None,
    end: datetime | None = None, all_day: bool = False, venue: str = "",
    address: str = "", url: str = "", image: str = "", categories: list[str],
    free: bool | None = None, price: str = "", description: str = "",
    extra: dict | None = None,
) -> dict:
    ev = {
        "id": make_id(source, str(raw_id)),
        "source": source,
        "title": clean(title, 160),
        "start": fmt(start),
        "end": fmt(end),
        "allDay": all_day,
        "venue": clean(venue, 120),
        "address": clean(address, 160),
        "url": url,
        "image": image,
        "categories": categories,
        "free": free,
        "price": clean(price, 60),
        "description": clean(description, 280),
    }
    if extra:
        ev.update(extra)
    return ev
