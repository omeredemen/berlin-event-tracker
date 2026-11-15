# Berlin – what's on

My personal Berlin event finder. It pulls socials, meetups, gallery openings, exhibitions, concerts, free events and club nights from several sites into one page. You can filter the list, star events into a plan and add them to your calendar.

```
config.json             ← what to fetch (sources, how many days ahead, your own calendar feeds)
fetcher/                ← Python script that collects + cleans + de-duplicates events
  fetch_events.py
  sources/*.py          ← one file per website
docs/index.html         ← the app (a single page, no build step)
docs/events.json        ← the data the app shows (rewritten by the fetcher)
.github/workflows/      ← refreshes events.json automatically 4× a day
tests/                  ← offline tests for every parser
```

## Sources

| Source | What you get | How |
|---|---|---|
| **kulturdaten.berlin** | Museums, exhibitions, readings, concerts, district events, lots of free things | Official open API from Berlin's culture department. No key needed |
| **Luma** (luma.com/berlin) | Community meetups, socials, networking, afterworks | The public feed the Luma website uses. Unofficial |
| **Eventbrite** | Socials, language exchanges, workshops, free events, arts | Structured data on Eventbrite's public Berlin search pages. Unofficial |
| **Resident Advisor** | Club nights and parties | The data feed the ra.co website uses. Unofficial |
| **Ticketmaster** | Concerts, comedy, shows | Official API. Needs a free key (see below) |
| **Your calendars** | Anything you follow: Meetup groups, Luma communities, galleries, venues | iCal (.ics) links that you add in `config.json` |

The unofficial sources are fine for a personal tool, but they can break whenever those sites change. If a source fails, the app keeps that source's events from the previous run. The source shows a red dot at the bottom of the page, and the other sources keep working.

## Setup (about 10 minutes, free)

1. **Create a GitHub repo** (public, so GitHub Pages is free) and upload everything in this folder.
   Only public event data goes into it. Your saved events and hidden events are stored in your browser, not in the repo.
2. **Turn on the app:** go to *Settings → Pages → Build and deployment*, choose *Deploy from a branch*, then *main* / `docs`, then *Save*.
   After about a minute your app is live at `https://<your-username>.github.io/<repo-name>/`.
3. **Allow the auto-refresh to save data:** go to *Settings → Actions → General → Workflow permissions* and select *Read and write permissions*.
4. **Run it once now:** in the *Actions* tab, open *Update events*, then click *Run workflow*. When it finishes, reload the app. The sample banner disappears and real events show up.
5. *(Optional)* **Ticketmaster concerts:** get a free key at <https://developer.ticketmaster.com> (create an app, then copy the "Consumer Key").
   In the repo, go to *Settings → Secrets and variables → Actions → New repository secret* and add `TICKETMASTER_API_KEY` with the key as its value.

On your phone, open the app URL and use *Share → Add to Home Screen* to get an app icon.

## Following your favourite groups and places (iCal feeds)

This is the best way to track specific things. In `config.json`, replace the two example entries under `ical_feeds`:

```json
{ "name": "Berlin Board Gamers", "url": "https://www.meetup.com/<group-name>/events/ical/", "categories": ["social"] }
```

Where to find feed links:
- **Meetup group:** usually `https://www.meetup.com/<group-name-from-the-url>/events/ical/`
- **Luma community:** open the calendar page, click *Subscribe*, and copy the iCal link
- **Galleries, venues, clubs:** look for "Subscribe", "iCal", "Add to calendar" or an `.ics` link on their events page
- **Any public Google Calendar:** *Settings → Integrate calendar → Public address in iCal format*

Categories you can use: `social`, `art`, `music`, `nightlife`, `talks`, `stage`, `other`. Add `"free": true` if everything in that feed is free.

## Running it on your own computer

```bash
pip install -r requirements.txt
python fetcher/fetch_events.py                 # all sources
python fetcher/fetch_events.py --only luma     # just one source
python -m http.server -d docs 8000             # then open http://localhost:8000
python tests/test_parsers.py                   # offline parser tests
```

Some sites block GitHub's servers but not home internet connections. If a source stays red in the app, run the fetcher on your own computer and push `docs/events.json`.

## Using the app

- **Date chips:** Today, Tomorrow, This weekend, Next 7 days, Everything (the next 30 days)
- **Category chips:** combine as many as you like. *Free only* hides anything that isn't free.
- **New since last visit:** shows only events that appeared since you last opened the app
- **☆ Save:** adds an event to *My plan*. You can download the whole plan as one calendar file.
- **⋯ menu:** add to Google Calendar, download an .ics file (Apple/Outlook), open in maps, see the event on other sites, or hide it
- **Ongoing exhibitions** are grouped in a collapsible box at the top so they don't fill up every day

## Changing things

- How far ahead to look: `days_ahead` in `config.json` (default 30)
- Turn a source off: set it to `false` under `sources`
- kulturdaten service listings (homework help, police advice, senior help desks…): `kulturdaten.skip_tags`. Set it to `[]` to keep everything
- Eventbrite categories: edit `eventbrite.pages`. The keys are the URL parts of Eventbrite search pages, e.g. `https://www.eventbrite.de/d/germany--berlin/networking/` → `networking`
- How events get sorted into categories: the keyword lists in `fetcher/common.py`
