# Country campaigns

Lithuania is preserved: `cities.json` (103 cities), `specialties.json` (238 terms), existing `results/leads.sqlite3` and exports in `../leads/lithuania/`.

```sh
python fast_leads.py --country lithuania --overnight
python fast_leads.py --country scotland --overnight --site-concurrency 8
python fast_leads.py --country scotland --describe
```

Scotland uses `campaigns/scotland.json` and 238 corresponding English terms in `campaigns/specialties-en.json`. It has separate state in `results/scotland/` and CSV exports in `../leads/scotland/`. Default country remains Lithuania for compatibility with the existing PowerShell launchers. Country records and existing Lithuanian exports are never copied into the Scotland database.

Source: [GeoNames GB gazetteer](https://download.geonames.org/export/dump/GB.zip), downloaded 2026-09-27, [CC BY 4.0 attribution](https://www.geonames.org/). Includes all 6,665 current populated places, small localities and populated-place sections in the extract with country GB, admin1 SCT and feature codes PPL/PPLA/PPLA2/PPLA3/PPLA4/PPLC/PPLL/PPLX. Excludes abandoned, destroyed and historical places. Administrative area, coordinates and GeoNames IDs distinguish same-named places. The file includes cities, towns, villages and neighbourhoods, not 6,665 officially designated cities. The source cannot guarantee every settlement or business; Maps can return nearby businesses and caps search results.

There are 1,586,270 place/specialty combinations. At 10 seconds each that is about 184 days before website checks and retries. This is an incremental long-running campaign, not a promise of a complete national directory. In the full plan, largest places run first within each specialty. Default safety caps are 1,000,000 businesses / 300,000 emails; override `--max-businesses` / `--max-emails` if required. Eight concurrent website checks and one Maps browser are used. Start with Scotland on the 2-vCPU/8-GB VPS; no England service is installed.

## Ubuntu VPS

Install Python venv support, create `.venv`, install `requirements.txt`, then run `.venv/bin/python -m playwright install --with-deps chromium`. Place this checkout at `/home/ubuntu/lt-leads`.

```sh
sudo cp deploy/scotland-leads.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now scotland-leads
sudo systemctl status scotland-leads --no-pager
tail -f /home/ubuntu/lt-leads/results/scotland/fast-leads.log
sudo systemctl stop scotland-leads
sudo systemctl start scotland-leads
```

The service resumes saved queries, starts after reboot and retries failures after 120 seconds. It is capped at 5 GB memory and 160% CPU (1.6 cores). `systemctl stop` requests graceful completion of the current query; use that rather than killing Python. SIGTERM creates the country-specific STOP file, which the service clears on start. CSV files contain the same two columns as the Lithuanian exports. Emails have domain DNS validation, not mailbox delivery verification. Review the log for failures and cap completion. No private keys, contacts or progress databases belong in Git.

## Organized exports and recovery

```text
leads/
  lithuania/
    all_leads.csv
    categories/
      kirpykla.csv
      ...
  scotland/
    all_leads.csv
    categories/
      hairdresser.csv
      ...
```

`all_leads.csv` contains unique country emails. Each category CSV contains emails for that category; the same email can belong to several categories. Only categories with saved contacts are exported. Rebuild every CSV without starting a browser:

```sh
python fast_leads.py --country lithuania --export-only
python fast_leads.py --country scotland --export-only
```

CSV files are written to a temporary file, flushed, then atomically replaced. SQLite WAL with FULL synchronous commits is the source of truth; interrupted CSV exports are rebuilt at startup. A query is completed only after its website tasks finish, and checked businesses are tracked per category. After a crash an unfinished query may be repeated; primary keys prevent duplicate emails. An OS process lock prevents concurrent writers for the same country and is released automatically on process death.

On the VPS systemd restarts crashes after 120 seconds. Four consecutive Maps failures force a fresh browser. Individual website tasks time out after 120 seconds; a watchdog restarts a process that fails to complete a query for 10 minutes. A manual `systemctl stop` remains stopped. A successful completed campaign or configured cap does not restart. Reboot starts the Scotland service and resumes its saved database. These protections handle process failures, not disk loss; preserve backups separately.

## Active Scotland month plan

The VPS service now uses `--country scotland --plan month --overnight`. It selects 160 populated towns (excluding urban subdivisions), including the largest settlement from each of all 32 council areas, with 148 consolidated English specialties. The complete original 6,665-place dataset remains available with `--plan full`.

The month plan has 23,680 queries. Phase 1 covers 40 towns including all council areas, phase 2 adds 40, and phase 3 adds 80. Queries alternate towns and specialties; the first 160 queries touch every selected specialty and the first 40 towns. Every selected town eventually receives every selected specialty. At an average 30/60/90 seconds per query, pure query processing takes approximately 8/16/25 days. These are scenarios, not a completion guarantee; network failures and rate limiting can extend processing.

A persistent SQLite deadline starts at the first scan and expires after 30 elapsed days, including downtime. Restarts never extend it. At expiry the runner finishes the current query, exports the results, and exits successfully; systemd leaves it stopped. If all queries finish earlier, it stops earlier. No promise of every Scottish business is made. `--describe` and `--export-only` do not start the clock.

Before switching campaigns, the old Scotland database, logs and exports were archived outside the live directories. Lithuania was not reset. Live outputs remain `../leads/scotland/all_leads.csv` and `../leads/scotland/categories/`.
