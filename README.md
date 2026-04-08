# Google Maps Lead Scraper

An async Playwright scraper that searches Google Maps across multiple metro areas and business categories, then exports outreach-ready leads.

The project targets **digitally underserved businesses** using this default qualification logic:
- No website
- Has a phone number
- Rating >= 3.0 (configurable)
- Reviews >= 5 (configurable)

## What It Does

- Iterates through metro/category pairs from `config/metros.py` and `config/categories.py`
- Searches Google Maps using queries like `plumbers in Houston TX`
- Opens each result and extracts business details
- Deduplicates businesses across all searches
- Writes:
  - `output/leads_raw.csv` (all unique businesses)
  - `output/leads_qualified.csv` (only qualified leads)
- Persists progress and checkpoints so runs can resume

## Project Structure

- `main.py` - Orchestrates the full run
- `scraper/` - Browser/session handling, Google Maps scraping, anti-detection helpers
- `data/` - Pydantic models, dedup logic, lead qualification, CSV export
- `persistence/` - Progress and checkpoint management
- `config/` - Metros, categories, and runtime settings
- `output/` - Generated CSVs, logs, progress files (created at runtime)

## Requirements

- Python 3.10+
- Windows/macOS/Linux
- Internet connection

Python packages are listed in `requirements.txt`.

## Setup

### 1) Create and activate virtual environment (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 2) Install dependencies

```powershell
pip install -r requirements.txt
```

### 3) Install Playwright browser binaries

```powershell
playwright install chromium
```

## Running the Scraper

From project root:

```powershell
python main.py
```

Useful options:

```powershell
# Run first 3 metros and first 2 categories (quick test)
python main.py --metros 3 --categories 2

# Run browser in headless mode
python main.py --headless

# Combine both
python main.py --metros 2 --categories 2 --headless
```

## How It Works (Execution Flow)

1. `main.py` loads settings, metros, and categories.
2. `BrowserManager` starts a Chromium context with random viewport/user-agent and stealth patches.
3. For each metro/category pair:
   - Builds query (`"<category> in <city>"`)
   - Detects possible CAPTCHA/block pages
   - Runs `search_and_scrape(...)` to collect businesses from Google Maps
4. Results pass through:
   - `Deduplicator` (removes already-seen businesses)
   - `filter_qualified(...)` (applies lead rules)
5. Data is appended to CSV outputs.
6. Progress/checkpoint files are updated so interrupted runs can continue.
7. Final summary is printed and browser is closed.

## Output Files

All outputs are written to `output/`:

- `leads_raw.csv` - Every unique business found
- `leads_qualified.csv` - Only businesses matching lead criteria
- `progress.json` - Pair-level status (`completed`, `in_progress`, `failed`)
- `seen_keys.json` - Dedup key registry across runs
- `checkpoints/*.json` - Per-pair temporary saved results
- `scraper.log` - Detailed logs

## Tuning and Customization

Edit `config/settings.py` to tune behavior:

- Detection resistance:
  - `HEADLESS`, `BROWSER_ARGS`
  - delay ranges (`SCROLL_DELAY_*`, `DETAIL_DELAY_*`, `SEARCH_DELAY_*`)
  - context refresh (`CONTEXT_REFRESH_EVERY`)
- Scrape limits:
  - `MAX_SCROLLS_PER_SEARCH`
  - timeouts (`DETAIL_LOAD_TIMEOUT_MS`, etc.)
- Lead quality thresholds:
  - `MIN_RATING`
  - `MIN_REVIEWS`

Edit targets:

- `config/metros.py` - metro areas
- `config/categories.py` - business categories

## Notes

- Google Maps markup can change over time. If extraction quality drops, selectors/parsing in `scraper/` may need updates.
- Scraping can trigger anti-bot checks; this project already includes random delays, stealth mode, periodic context refresh, and block detection, but no approach is guaranteed.
- Use responsibly and ensure compliance with applicable laws and platform terms in your region.

