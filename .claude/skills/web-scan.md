---
name: web-scan
description: Run the themed open-call/prize/residency search queries via WebSearch, judge relevance and freshness directly, and append genuinely new leads into sources.yaml's claude_web_scan_leads manual entries.
---

Manual replacement for the disabled `google_search_opportunities` source (Google
removed "search the entire web" for new free Programmable Search Engines, so
that adapter can no longer do a real web-wide search — see the notes on that
entry in `sources.yaml`). This skill does the same job by hand, using the
WebSearch tool already available in this environment, whenever the user asks
for it (e.g. "run a web scan", "/web-scan").

## Procedure

1. Run these 20 themed queries (also stored in `sources.yaml`'s disabled
   `google_search_opportunities` entry, `parser_options.search_queries` —
   that's the canonical, editable copy; if the two ever drift, that file
   wins and this list should be updated to match):

   Practice/format (original 10):
   - `"open call" "media art"`
   - `"artist residency" "media art"`
   - `"artist commission" "digital art"`
   - `"open call" "new media art"`
   - `"artist residency" installation`
   - `"artist commission" interactive installation`
   - `"open call" "computational art"`
   - `"creative coding" residency`
   - `"art prize" "digital art"`
   - `"open call" "data art"`

   Civic/critical-tech themes + underrepresented listing types (added
   2026-07-28 to cover practice areas the original 10 never searched for):
   - `"open call" "civic tech"`
   - `"open call" "open data"`
   - `"artist residency" "urban data"`
   - `"open call" "AI art"`
   - `"artist residency" "artificial intelligence"`
   - `"artist grant" "digital art"`
   - `"artist fellowship" "media art"`
   - `"open call" "algorithmic"`
   - `"open call" "institutional critique"`
   - `"open call" "data justice"`

   Add the current year to each query (e.g. append ` 2026`) so results skew
   toward the current cycle rather than past years' calls.

2. Also read the current `claude_web_scan_leads.manual_entries` list (in the
   same file) and skim `docs/data/listings.json` URLs, so you know what's
   already tracked and can skip re-adding it.

3. Run each query with WebSearch. For each result, judge — using your own
   understanding of the user's practice (new media/digital/data art, civic
   tech, open data, urban data, algorithmic accountability, forensic
   architecture, institutional critique, creative coding, computational
   art/design, interactive/sound/media installation, AI — see
   `scraper/discipline_tags.py` and `relevance_allowlist.yaml` for the
   current keyword vocabulary if you want a sanity check, but don't just
   keyword-match; use judgment) — whether it's:
   - an actual open call, prize, residency, or grant (not a news article,
     a past recap, or an unrelated page)
   - plausibly relevant to that practice
   - not already closed (if a deadline is stated or discoverable, it should
     be today or later; if the page reads as stale/old with no current
     cycle, skip it)
   - not a duplicate of a URL already in `claude_web_scan_leads` or already
     present in `docs/data/listings.json`

4. For each surviving new lead, fetch the page (WebFetch) if useful to pin
   down organizer, a real deadline (`YYYY-MM-DD` if determinable), country,
   eligibility, and a short description — don't guess fields you can't
   support from the page.

5. Append each as an entry under `claude_web_scan_leads.manual_entries` in
   `sources.yaml`, matching the shape `scraper/adapters/manual.py` expects:
   ```yaml
   - title: "..."
     organizer: "..."
     country: "UK"            # or null if unclear — omit the key rather than guess
     region_tier: high         # optional override; omit to derive from country
     url: "https://..."
     listing_type: "open_call" # open_call | prize | residency | grant
     deadline: "2026-09-30"    # omit if not determinable
     eligibility: "..."        # optional
     notes: "..."              # short context, becomes the description field
   ```

6. Run `python -m scraper.run --dry-run --cadence all` to regenerate
   `docs/data/listings.json`/`meta.json` and confirm the new entries appear
   correctly (right tier, discipline tags, status).

7. Report a short summary to the user: how many queries ran, how many
   results were judged relevant, how many were genuinely new vs. already
   tracked, and what got added.

8. Commit (`sources.yaml` + `docs/data/*.json`) and push — this stands in
   for what the automated scraper would otherwise commit, so treat it the
   same way (plain data commit, no need to ask permission for the commit
   itself, but do surface the diff/summary so the user can see what was
   added).

## Notes

- This is manual/on-demand, not scheduled — it only runs when explicitly
  invoked in a session, unlike the weekly/quarterly GitHub Actions cron for
  every other source.
- No API keys, no billing, no extra accounts — it uses the WebSearch tool
  already available in this environment.
- Judge relevance directly rather than reusing `passes_strong_filter()` —
  that keyword allowlist exists because scraped aggregator sources have no
  human-in-the-loop; here you already are the judgment call.
