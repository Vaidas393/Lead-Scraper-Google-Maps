# Country campaigns

Lithuania is preserved: `cities.json` (103 cities), `specialties.json` (238 terms), existing `results/leads.sqlite3` and `../leads/`.

```sh
python fast_leads.py --country lithuania --overnight
python fast_leads.py --country scotland --overnight --site-concurrency 8
python fast_leads.py --country scotland --describe
```

Scotland uses `campaigns/scotland.json` and 238 corresponding English terms in `campaigns/specialties-en.json`. It has separate state in `results/scotland/` and CSV exports in `../leads-scotland/`. Default country remains Lithuania for compatibility with the existing PowerShell launchers. Country records and existing Lithuanian exports are never copied into the Scotland database.

Source: [GeoNames GB gazetteer](https://download.geonames.org/export/dump/GB.zip), downloaded 2026-09-27, [CC BY 4.0 attribution](https://www.geonames.org/). Includes all 6,665 current populated places, small localities and populated-place sections in the extract with country GB, admin1 SCT and feature codes PPL/PPLA/PPLA2/PPLA3/PPLA4/PPLC/PPLL/PPLX. Excludes abandoned, destroyed and historical places. Administrative area, coordinates and GeoNames IDs distinguish same-named places. The file includes cities, towns, villages and neighbourhoods, not 6,665 officially designated cities. The source cannot guarantee every settlement or business; Maps can return nearby businesses and caps search results.

There are 1,586,270 place/specialty combinations. At 10 seconds each that is about 184 days before website checks and retries. This is an incremental long-running campaign, not a promise of a complete national directory. Largest places run first within each specialty. Default safety caps are 1,000,000 businesses / 300,000 emails; override `--max-businesses` / `--max-emails` if required. Eight concurrent website checks and one Maps browser are used. Start with Scotland on the 2-vCPU/8-GB VPS; no England service is installed.

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
