# Google Maps Lead Scraper

An async Playwright scraper that pulls outreach-ready business leads out of Google Maps. Point it at **any city or area in the world**, choose how deep to dig, and watch it run in a live terminal dashboard.

## Why depth matters

Google Maps returns **at most ~120 results per search**. That cap is the single biggest limit on how many leads you can get, and the only way around it is to issue more, narrower searches. This scraper gives you three strategies, chosen per run:

| Depth | What it does | Searches per category | When to use |
|---|---|---|---|
| **City** | One search for the whole city | 1 | Quick sampling, small towns |
| **Areas** | Discovers the city's suburbs/neighbourhoods/postal areas from Google Maps itself, then searches each one | 1 per sub-area (default 12) | **Default choice.** Typically 5-15x more results |
| **Grid** | Tiles the map with lat/lng cells and pins each search to a cell | 1 per tile (e.g. 9 for 3x3) | Maximum coverage, dense metros |

Sub-areas are derived from Maps itself — one cheap probe search, then the localities and postal codes are ranked out of the resulting addresses. No geocoding API, no key, works in any country.

## Lead profiles

What counts as a "qualified lead" is chosen at setup:

- **`no_website`** *(default)* — businesses with no website at all. Classic "let me build you a site" outreach.
- **`no_email`** — businesses that have a site but no findable email. Crawls the site (plus `/contact`, `/about`) for contact details and social profiles.
- **`all`** — qualify nothing, export everything, filter later.

Shared thresholds (configurable): minimum rating, minimum review count, and whether a phone number is required. A missing rating or review count is *not* disqualifying — plenty of real small businesses have neither.

## Setup

Requires Python 3.10+.

```bash
python -m venv .venv
```

```bash
.venv\Scripts\Activate.ps1
```

```bash
pip install -r requirements.txt
```

```bash
playwright install chromium
```

## Running

Just run it — you get an interactive wizard, then a live dashboard:

```bash
python main.py
```

The wizard asks for the place, depth, categories, lead profile, thresholds, headless mode and proxy, then shows a summary with the search count and a time estimate before anything starts.

### Check it still works

Google rotates its obfuscated CSS classes on its own schedule. Before a long run:

```bash
python main.py --doctor
```

This opens one live search and reports which selectors still match. It distinguishes **"the markup changed"** from **"you're being blocked"** — two problems that look identical from an empty CSV but need completely different fixes.

### Non-interactive examples

```bash
python main.py --city "Austin TX" --depth areas --categories plumbers electricians
```

```bash
python main.py --city Lahore --depth areas --categories dentists --headless
```

```bash
python main.py --city "Miami FL" --depth grid --grid 4x4 --grid-span 25
```

```bash
python main.py --metro Houston --profile no_email --min-rating 4.0
```

### CLI options

**Target**
- `--city TEXT` (alias `--area`) — any place Google Maps understands
- `--metro NAME` — a built-in US metro preset, e.g. `--metro Houston`
- `--categories CAT [CAT ...]` — defaults to the built-in list (`--list-categories`)
- `--depth {city,areas,grid}`

**Lead quality**
- `--profile {no_website,no_email,all}`
- `--min-rating FLOAT`, `--min-reviews INT`, `--no-require-phone`
- `--no-website-crawl` — never open business websites (much faster; skips email/social discovery)

**Scope**
- `--max-areas N` — sub-areas to search at `--depth areas`
- `--grid RxC`, `--grid-span KM` — grid shape and coverage
- `--max-results N` — cap results per search

**Runtime**
- `--headless`, `--proxy URL`, `--output DIR`
- `--concurrency N` — run N browsers in parallel (default 1). Faster, but N times the request rate and a correspondingly higher block risk.
- `--no-resume` — ignore saved progress and re-scrape
- `--no-tui` — plain logs instead of the dashboard
- `-y` / `--yes` — skip the wizard

**Tools**
- `--doctor`, `--list-categories`

Every setting also has a `SCRAPER_`-prefixed environment variable (`SCRAPER_MIN_RATING`, `SCRAPER_HEADLESS`, `SCRAPER_PROXY`, `SCRAPER_OUTPUT_DIR`, delay ranges, timeouts, ...). See `config/settings.py`.

## Output

Written to `output/` (or `--output`):

- **`leads_raw.csv`** — every unique business found
- **`leads_qualified.csv`** — only those matching the active lead profile
- **`leads.xlsx`** — both of the above as a two-sheet workbook
- `progress.json`, `seen_keys.json`, `checkpoints/` — resume state
- `scraper.log` — full DEBUG log

Columns: Name, Category, Address, Phone, Business Email, Rating, Reviews, Has Website, Website URL, Facebook, Instagram, LinkedIn, Claimed, Hours, Price Level, Latitude, Longitude, Plus Code, Place ID, Google Maps URL, City, Area, Metro Area, State, Search Query, Scraped At.

If an existing CSV has an older column set, it is archived as `leads_raw.legacy-<timestamp>.csv` rather than being appended to with mismatched columns.

## Resuming

Runs are resumable at two levels:

- **Per search** — completed searches are skipped on the next run.
- **Within a search** — a checkpoint records which results have been scraped, so a crash 100 businesses in costs one result, not all of them.

State is written atomically (temp file + rename) and flushed periodically, so a hard kill, Ctrl-C or `docker stop` cannot corrupt it or lose the run's dedup pool. Re-run the same command to continue; pass `--no-resume` to start over.

Deduplication uses Google's own place ID when available (exact), falling back to a normalized name + phone/address composite that treats "Joe's Pizza LLC" / "Joes Pizza" and "123 Main St" / "123 Main Street" as the same business.

## Anti-blocking

Included: stealth patches, randomized viewport and Chromium user agent, a timezone matched to the region being scraped, randomized delays and idle pauses, periodic browser-context rotation, retries with exponential backoff, block detection **during** a search as well as before it, escalating backoff on repeated blocks, and an abort threshold so a blocked run stops rather than hammering the same IP.

Proxy support is optional (`--proxy` or `SCRAPER_PROXY`) but strongly recommended for large runs. On a block the run backs off with escalating pauses, rotates browser identity and retries the search once; after `SCRAPER_MAX_CONSECUTIVE_BLOCKS` (default 4) it stops rather than keep hammering the same IP.

`--concurrency N` runs N independent browsers over the search queue. It is genuinely faster, but it multiplies your request rate by N — leave it at 1 unless you are using proxies.

**None of this is a guarantee.** If you get blocked, slow the delays down (`SCRAPER_SEARCH_DELAY_MIN`), run headful, and use a proxy.

## Project structure

```
main.py           Entry point: arg parsing, wizard, summary
runner.py         Run orchestration, resilience, resume
reporting.py      Run stats + the reporter interface
config/           Settings, enums, per-run config, output paths, presets
geo/              Target resolution, sub-area discovery, grid tiling, planning
scraper/          Browser, selectors, extraction, scrolling, retries, doctor
data/             Models, normalization, dedup, qualification, export
persistence/      Atomic JSON, progress, checkpoints
ui/               Wizard and live dashboard
tests/            Offline unit tests
```

## Tests

```bash
python -m pytest
```

The suite is fully offline — parsers, normalization, dedup keys, grid maths, area ranking, lead profiles, CLI parsing, retry semantics and export behaviour. It does not touch the network. For a live check, use `--doctor`.

## Docker

```bash
docker compose up
```

There is no TTY in the container, so the dashboard automatically falls back to plain logs. Set your target via environment or override the command:

```bash
docker compose run --rm scraper python main.py --city "Austin TX" --depth areas -y
```

Results land in `./results` on the host.

## Notes

- Google Maps markup changes over time. All selectors live in `scraper/selectors.py`, every lookup walks a fallback chain, and semantic attributes (`role`, `aria-label`, `data-item-id`) are preferred over obfuscated CSS classes. `--doctor` tells you within seconds when something breaks.
- Sponsored placements are filtered out of the results feed — an ad is not a lead.
- Use responsibly and ensure compliance with applicable laws and platform terms in your region.
