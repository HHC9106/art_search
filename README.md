# Art Open Calls & Prizes Tracker

A personal tool that scrapes art open calls, prizes, residencies, and grants,
ranks them by a nation/region priority tier (top/high/medium/low, user-defined
— see below), and lets you browse/track them in a static dashboard.

See [PLANNING.md](PLANNING.md) for the full design rationale.

## How it works

- `.github/workflows/scrape.yml` runs weekly (plus a quarterly pass for
  single-institution "watch" sources), executes `scraper/run.py`, and commits
  the results straight into `docs/data/listings.json` / `docs/data/meta.json`.
- GitHub Pages serves `docs/` directly — the dashboard (`docs/index.html` +
  `docs/app.js`) reads that same JSON file client-side.
- Application/tracking status (interested, applied, etc.), tier overrides, and
  removed listings are stored in your browser's `localStorage` only — the
  scraper and GitHub Actions have no access to it, so it never syncs across
  devices or browsers on its own. See "Backing up dashboard state" below for
  how to carry it over manually.
- **Tier is nation/region-based by default and fully user-editable.**
  `tier_config.yaml` sets the server-side default per country (used at scrape
  time and for the email digest), but the dashboard's Tier column is a live
  per-listing dropdown: changing it only affects that one row (stored in
  `localStorage`, so it's a personal/per-device setting — "Reset tier
  overrides" clears it). Countries not in `tier_config.yaml` fall back to its
  `default` (currently `medium`).
- A weekly email digest (new listings, a one-time "heads up" ~30 days before
  a deadline, and an "urgent" notice within 7 days) is sent via Gmail SMTP.

## Backing up dashboard state

Tracking status, tier overrides, and removed listings all live only in your
browser's `localStorage` (see "How it works" above) — there's no backend to
sync them anywhere automatically. To back them up or carry them to a new
browser/device:

1. On the dashboard, click **Export backup** — downloads everything
   (tracking + tier overrides + removed listings) as one JSON file.
2. Save/overwrite it as `local-state-backup.json` at the repo root (a
   placeholder with empty state already exists there so the convention is
   established from the start).
3. Commit and push that file whenever you want it backed up on GitHub — or
   just ask Claude to do it next time you're working in this repo; it's a
   plain tracked file, not gitignored, specifically so it can be committed
   like any other change.
4. To restore on a different browser/device, click **Import backup** and
   pick that same file.

This is a manual, on-demand backup — not a live sync. Nothing about your
dashboard interactions is ever pushed automatically; you decide when to
export and when to commit.

## Setup (one-time)

1. **Add real sources.** `sources.yaml` currently only contains placeholder
   entries (`enabled: false`, `url: "TBD"`). For each real site you want to
   track, fill in the URL and, for `html`/`playwright` adapters, the CSS
   selectors in `parser_options` (see the fixture example in
   `tests/fixtures/sample_listing_page.html` /
   `tests/test_adapters.py` for the expected shape). Set `enabled: true` once
   verified locally (see "Running locally" below).

2. **Enable GitHub Pages.** Repo Settings → Pages → Source: "Deploy from a
   branch" → Branch: `main`, folder: `/docs`. (Requires the repo to be
   public on the free tier.)

3. **Add repository secrets.** Repo Settings → Secrets and variables →
   Actions → New repository secret:
   - `GMAIL_ADDRESS` — the Gmail account to send from
   - `GMAIL_APP_PASSWORD` — a 16-character
     [App Password](https://myaccount.google.com/apppasswords) (requires 2FA
     enabled on the account)
   - `EMAIL_TO` — where the digest should be sent
   - `GOOGLE_SEARCH_API_KEY` / `GOOGLE_SEARCH_ENGINE_ID` — only needed for the
     `google_search_opportunities` source, which runs themed queries through
     Google's Custom Search JSON API (not scraped HTML — direct scraping of
     Google Search is blocked and against their ToS). Get a Search Engine ID
     from [Programmable Search Engine](https://programmablesearchengine.google.com/)
     (configure it to search the entire web) and an API key from a Google
     Cloud project with the Custom Search API enabled. Free tier: 100
     queries/day — this source uses 10 per run. Without these two secrets set,
     this one source just errors out cleanly each run (logged, not a crash);
     everything else keeps working.

4. **Trigger the workflow manually once** (Actions tab → "scrape-and-publish"
   → Run workflow) to confirm everything works end-to-end before trusting
   the weekly schedule.

## Running locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r scraper/requirements.txt
python -m playwright install chromium   # only needed if any source uses adapter: playwright
```

Copy `.env.example` to `.env` and fill in real values if you want to test
email sending locally (never commit `.env` — it's gitignored).

**Dry-run the scraper** (writes `docs/data/listings.json`/`meta.json`, skips
email):
```bash
python -m scraper.run --dry-run
```

**Preview the dashboard** against whatever is currently in `docs/data/`:
```bash
python -m http.server 8000 -d docs
# open http://localhost:8000
```

**Preview the email digest** without sending anything:
```bash
python -m scraper.notify --preview-file=preview.html
open preview.html
```

**Send one real test email** (reads `GMAIL_*`/`EMAIL_TO` from `.env`):
```bash
python -m scraper.notify --send-test
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Tests are fixture-based and never make live network calls — `tests/test_run.py`
exercises the full scrape→upsert→status pipeline using the `manual` adapter
against temp files, and `tests/test_adapters.py` exercises the HTML
extraction logic against a saved sample page in `tests/fixtures/`.

## Adding a new source

In the common case this is a pure `sources.yaml` edit — no code change:

```yaml
- name: my_new_source          # stable snake_case key, never rename once enabled
  display_name: "My New Source"
  organizer: "Some Org"
  country: "UK"
  adapter: html                # rss | html | playwright | manual | custom
  url: "https://example.org/opportunities"
  enabled: true
  parser_options:
    item_selector: ".opportunity"
    title_selector: ".title"
    link_selector: ".title a"
    deadline_selector: ".deadline"
```

- Try `rss` first if the site has a feed — no selectors needed, deadlines are
  best-effort parsed from the entry summary.
- Use `html` for plain server-rendered pages via CSS selectors.
- Use `playwright` only if the listing content requires JS rendering (slower,
  and more fragile — reserve for sites that truly need it).
- Use `manual` for newsletter-only leads with no scrapable page — add entries
  under `manual_entries:` directly in `sources.yaml`.
- Only write a bespoke `scraper/adapters/custom/<name>.py` module (exposing a
  `collect(config)` function) if a site is too irregular for the generic
  adapters to express via `parser_options`.

If a source turns out to be bot-protected or unreliable to scrape, fall back
to a `manual` entry rather than fighting an anti-detection arms race.
