# Art Open-Call & Prize Tracker — Implementation Plan

## Context

The user is a working artist who wants to stop manually checking scattered websites/newsletters for art open calls, prizes, residencies, and grants. They want a personal tool that aggregates listings, ranks them by region priority (UK highest, US/Europe/Taiwan as tier 2, everything else tier 3), lets them track application status per listing, and emails a digest of new/soon-due items.

The repo (`art_search`, tracked at `github.com/HHC9106/art_search`) started out empty — only a mismatched Jekyll `.gitignore` and MIT `LICENSE` from GitHub's repo-creation flow. This was a greenfield build.

Key constraints locked in with the user:
- **Python** for the scraper/backend.
- **Zero paid hosting** — GitHub Actions + GitHub Pages only, no VPS/DB service.
- **Web dashboard** (not CLI-only, not Notion/Airtable).
- **Email digest** via the user's own Gmail App Password.
- **Single-device use** — tracking status (interested/applied/etc.) does not need to sync across devices, so it can live entirely in browser `localStorage` with no backend database.
- **Repo is public** (required for free GitHub Pages) — acceptable since content is just public org names/URLs/deadlines.
- **Weekly scrape cadence**, with a two-tier deadline warning: a one-time "heads up" around 30 days out, and a second, separate "urgent" notice within 7 days of the deadline — not a repeated weekly nag for the same listing.
- Source websites for UK/US/EU/Taiwan will be supplied by the user later; the plan proposes a small illustrative starting list marked TBD, and the source system must be pluggable (add a source = edit YAML, not write code, in the common case).

The intended outcome: push to `main` once, configure two GitHub secrets and the Pages source, and from then on the repo maintains itself — a bot commits fresh listings weekly and emails what's new/urgent, while the user browses/filters/tracks via a static dashboard.

## Architecture

**GitHub-as-backend, fully static:**
- `.github/workflows/scrape.yml` runs weekly (`workflow_dispatch` also enabled for manual runs): checks out the repo, runs the Python scraper, writes results directly into `docs/data/listings.json` + `docs/data/meta.json`, sends the email digest, and — only if the data actually changed — commits back under a bot identity and pushes.
- GitHub Pages serves straight from `main` / `/docs` (classic "deploy from branch" mode — no build step, so the push itself triggers the redeploy, no extra Actions-based deploy job needed).
- The dashboard (`docs/index.html` + `docs/app.js`) fetches `data/listings.json` client-side, merges in per-listing tracking state from `localStorage`, and does all filtering/sorting/searching in the browser.

This means `docs/data/listings.json` is simultaneously the scraper's output, the version-controlled history (via git blame/log), and the exact file the live dashboard reads — no separate "data layer" to keep in sync.

## Repo layout

```
art_search/
├── .github/workflows/scrape.yml   # weekly cron + workflow_dispatch
├── scraper/
│   ├── models.py                  # Listing dataclass, stable id hashing
│   ├── tier.py                    # region_tier(country) -> 1/2/3
│   ├── sources_config.py          # loads/validates sources.yaml
│   ├── adapters/
│   │   ├── base.py                # SourceAdapter protocol + factory
│   │   ├── rss.py                 # generic feedparser adapter
│   │   ├── html.py                # generic requests+BeautifulSoup adapter (CSS selectors from config)
│   │   ├── playwright_adapter.py  # generic JS-rendering adapter, used only where required
│   │   ├── manual.py              # hand-curated YAML entries (newsletter-only leads, etc.)
│   │   └── custom/                # bespoke per-site adapters, only for sites too irregular for generic config
│   ├── run.py                     # orchestration entrypoint
│   ├── notify.py                  # builds/sends the email digest
│   └── requirements.txt
├── sources.yaml                    # pluggable source config, see below
├── docs/                           # GitHub Pages root
│   ├── index.html
│   ├── app.js                      # fetch + merge localStorage + render/filter/sort
│   ├── style.css
│   └── data/
│       ├── listings.json           # committed source-of-truth AND what Pages serves
│       └── meta.json               # last run time, per-source health, counts
├── tests/                          # fixture-based, no live network calls
├── .env.example
├── .gitignore                      # replaced the Jekyll template with a Python one (+ .env)
└── README.md                       # setup + "how to add a new source"
```

## Data model (`scraper/models.py`)

`Listing`: `id` (stable — first 16 hex chars of `sha256(source_name:url)`, so re-runs upsert instead of duplicating), `title`, `organizer`, `source_name`, `url`, `country`, `region_tier` (1/2/3, computed by `tier.py` unless overridden), `discipline` (list), `listing_type` (`open_call`/`prize`/`residency`/`grant`), `deadline` (date or null), `deadline_raw` (original text, kept if parsing fails), `fee`, `fee_currency`, `fee_waiver_available`, `prize_amount` (free text — prizes are rarely a clean number), `eligibility`, `description`, `tags`, `status` (`open`/`closed`, recomputed every run), `first_seen_date`, `last_seen_date`, `last_checked_date`, `raw_extra` (free-form dict so one odd field from one source never forces a schema migration).

**Notification state**: each `Listing` also carries `notified_tier` (`none`/`month`/`urgent`) and `last_notified_date`. `notify.py` updates these after sending and they get committed along with everything else — this is what prevents re-alerting on the same listing every single week once it's already been flagged at a given tier.

## `sources.yaml`

Each entry: `name` (stable snake_case key, used in id hashing — never rename once enabled), `display_name`, `organizer`, `country`, `region_tier` (usually `null` → derived from `country`), `adapter` (`rss`/`html`/`playwright`/`manual`/`custom`), `url`, `enabled` (bool), `parser_options` (adapter-specific — e.g. CSS selectors for `html`), `notes`.

Adding a real source later is just a new YAML block (plus maybe `parser_options` tuning) — no code change, unless a site is irregular enough to need a `custom/` adapter.

**Initial candidate list** (unconfirmed placeholders, `enabled: false`, `url: "TBD"` — the user will supply/verify real ones):
- **Tier 1 (UK):** a-n The Artists Information Company, Arts Council England, Axisweb, Curator Space
- **Tier 2 (US/EU/Taiwan):** CaFÉ/CallForEntry.org (flagged as likely needing the manual-curation fallback if bot-protected), Res Artis, e-flux announcements, Taiwan Ministry of Culture, National Culture and Arts Foundation (NCAF)
- **Tier 3:** none proposed — it's the automatic fallback for any country not in the tier 1/2 sets

## Scraper orchestration (`scraper/run.py`)

1. Load `sources.yaml`, skip disabled entries.
2. Load previous `docs/data/listings.json` as prior state.
3. For each enabled source, independently `try/except` — one broken adapter never fails the whole run; failures are logged for `meta.json` and the email's source-health footer.
4. Upsert into the merged state by `id`: preserve `first_seen_date` on existing ids, update everything else, advance `last_seen_date`/`last_checked_date`.
5. Recompute `status`: `closed` if `deadline < today`, or if a listing stops appearing across several consecutive successful checks of its source (handles silent removal).
6. Sort the written file by `id` (not by tier/deadline) so git diffs stay minimal — ranking is purely a frontend concern, computed in `app.js`.
7. Write `docs/data/listings.json` + `docs/data/meta.json`.
8. Call `notify.build_and_send(...)` in-process using this run's new/heads-up/urgent computations (below).

**Fallback order per source** to avoid an anti-bot arms race: RSS/Atom feed → plain HTML via `requests`+BeautifulSoup → Playwright only where JS rendering is unavoidable → manual curated YAML entry if scraping proves unreliable. Always send a descriptive User-Agent with contact info, respect `robots.txt`, and space out requests.

## Tier & ranking logic (`scraper/tier.py`)

```python
TIER_1 = {"uk", "united kingdom", "england", "scotland", "wales", "northern ireland", "gb"}
TIER_2 = {"us", "usa", "united states", "taiwan", "tw"} | EU_COUNTRY_NAMES

def region_tier(country, override=None):
    if override is not None: return override
    c = (country or "").strip().lower()
    if c in TIER_1: return 1
    if c in TIER_2: return 2
    return 3
```

Default dashboard sort: `region_tier` asc → `deadline` asc (no-deadline listings sort last within their tier) → `status` (open before closed). User can switch to deadline-only / prize-amount / recently-added.

## GitHub Actions workflow

- Triggers: `schedule` (weekly, e.g. Monday 06:00 UTC) + `workflow_dispatch`. A `push` trigger on `scraper/**`/`sources.yaml`/workflow changes only (explicitly excluding `docs/data/**`) so the bot's own data commits can never retrigger the workflow.
- `permissions: contents: write`.
- Steps: checkout → setup Python 3.12 (pip cache) → `pip install -r scraper/requirements.txt` → cache + install Playwright's Chromium → `python -m scraper.run` (env: `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `EMAIL_TO` secrets) → conditional commit (`git add docs/data/*.json && git diff --cached --quiet || git commit ... && git push`) using a bot identity (`github-actions[bot]`), message `chore(data): update listings [skip ci]`.
- Secrets to configure: `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD` (16-char Gmail App Password, requires 2FA), `EMAIL_TO=andyentre@gmail.com`.
- Pages: Settings → Pages → Deploy from branch → `main` / `/docs`. No separate deploy job needed.

## Frontend & localStorage tracking

- `app.js`: `fetch('data/listings.json', {cache: 'no-store'})`, then merge in `localStorage.getItem('art-search-tracking')` — a JSON map `{ "<listingId>": { status: "interested|applied|rejected|accepted|ignored", note, updated_at } }` — defaulting to `status: "none"` for unmarked listings. Nothing is ever written back to the JSON file, only to `localStorage`.
- UI: tier filter chips, discipline/listing-type filters, open/closed filter, tracking-status filter, text search, sort dropdown, "last updated" badge from `meta.json`, per-row tracking controls + note field, link-out to source.
- Since cross-device sync isn't needed, add a simple manual export/import button (download/upload the localStorage JSON) as a backup — not automated.

## Email digest logic (`scraper/notify.py`)

Three sections, computed fresh each run against the persisted `notified_tier`/`last_notified_date` fields (this is what makes the two-tier warning fire once each, not every week):
- **New this run**: `first_seen_date == today`, grouped by tier.
- **Heads up (~30 days out)**: `status == open`, `deadline` set, `days_left <= 30`, and `notified_tier` not yet `month` or `urgent` → include, then set `notified_tier = "month"`.
- **Urgent (within 7 days)**: `status == open`, `deadline` set, `days_left <= 7`, and `notified_tier != "urgent"` → include, then set `notified_tier = "urgent"`.
- **Source health footer**: any source that errored this run, with the error message.
- Skip sending entirely if all three sections are empty (no noise on quiet weeks).
- Sent via `smtplib` + STARTTLS to `smtp.gmail.com:587`, logging in with the Gmail App Password; send failures are caught/logged, never fail the job (data still commits either way).

**Accepted tradeoff (v1):** because tracking status lives only in browser `localStorage`, the email digest can't filter to "only things I marked interested" — it's an aggregate new/heads-up/urgent list across everything scraped. Revisit only if this proves too noisy in practice.

## Verification plan

- **Local scraper dry run:** `python -m scraper.run --dry-run` writes `docs/data/listings.json` locally and skips sending email (no secrets needed).
- **Unit tests** (`tests/`, fixture-based, no live network): `test_tier.py` (country→tier), `test_models.py` (id-hash stability + upsert/merge across two synthetic snapshots), `test_notify.py` (new/heads-up/urgent selection logic against a fixed "today" and pre-set `notified_tier` values, confirming no repeat alert within the same tier).
- **Local dashboard preview:** `python -m http.server 8000 -d docs`, open `localhost:8000` — identical relative paths to production, since `listings.json` already lives under `docs/data/`.
- **Email dry run:** `notify.py --dry-run --preview-file=preview.html` renders the digest to a local file without sending; `--send-test` sends one real email using a local gitignored `.env` to confirm Gmail SMTP auth before trusting CI secrets.
- **End-to-end Actions test:** add the 3 secrets, push, manually trigger via `workflow_dispatch`, confirm per-source pass/fail in the run summary, confirm `docs/data/*.json` committed under the bot identity, confirm Pages redeployed and the live dashboard reflects new data, force a test notification (temporarily seed a manual entry or lower the day thresholds) to confirm the email arrives and renders correctly, then let it run unattended for a couple of real weekly firings before fully trusting the schedule.

## Status

- [x] Core library: `models.py`, `tier.py`, `sources_config.py`, adapters (`rss`/`html`/`playwright`/`manual`/`custom`), placeholder `sources.yaml` — smoke-tested locally.
- [x] `run.py` orchestration (upsert/merge, staleness-based closing, per-source error isolation)
- [x] `notify.py` email digest (new/heads-up/urgent tiers, no repeat alerts)
- [x] Static dashboard (`docs/`) — verified headlessly (filters, tier badges, localStorage tracking, no console errors)
- [x] GitHub Actions workflow (`.github/workflows/scrape.yml`)
- [x] Tests — 26 passing, fixture-based, no live network calls
- [x] README
- [ ] Real source URLs from the user for `sources.yaml` (still needed — everything is built to accept them as plain config with no architecture changes)
- [ ] Not yet committed/pushed to GitHub — first commit, Pages settings, and Actions secrets are pending user go-ahead
