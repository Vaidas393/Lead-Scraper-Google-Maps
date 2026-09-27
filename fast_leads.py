"""Local, restartable public-contact collector. No model/API tokens required."""
from __future__ import annotations

import asyncio
import argparse
import csv
import html
import ipaddress
import json
import logging
from logging.handlers import RotatingFileHandler
import re
import sqlite3
import sys
import signal
import time
from contextlib import suppress
from email.utils import parseaddr
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import dns.resolver
import dns.asyncresolver
import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from scraper.browser import BrowserManager
from scraper.parsers import is_valid_email

def parse_options():
    parser = argparse.ArgumentParser(description="Collect public business contacts, with separate country progress.")
    parser.add_argument("--country", choices=("lithuania", "scotland"), default="lithuania")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--test-limit", type=int, default=10)
    mode.add_argument("--pilot-specialties", type=int)
    mode.add_argument("--overnight", action="store_true")
    parser.add_argument("--site-concurrency", type=int, default=8)
    parser.add_argument("--max-businesses", type=int, default=1000000)
    parser.add_argument("--max-emails", type=int, default=300000)
    parser.add_argument("--describe", action="store_true", help="Show campaign without starting or writing progress")
    return parser.parse_args()

options = parse_options()
COUNTRY = options.country
if COUNTRY == "lithuania":
    PROFILE = {"country": "Lithuania", "gl": "lt", "locale": "lt-LT", "timezone": "Europe/Vilnius"}
    CITIES = json.loads((ROOT / "cities.json").read_text(encoding="utf-8-sig"))["cities"]
    SPECIALTIES_FILE = ROOT / "specialties.json"
    OUT_DIR = ROOT.parent / "leads"
    RESULTS = ROOT / "results"
    STOP = ROOT / "STOP"
else:
    PROFILE = json.loads((ROOT / "campaigns" / f"{COUNTRY}.json").read_text(encoding="utf-8"))
    CITIES = PROFILE["cities"]
    SPECIALTIES_FILE = ROOT / "campaigns" / "specialties-en.json"
    OUT_DIR = ROOT.parent / f"leads-{COUNTRY}"
    RESULTS = ROOT / "results" / COUNTRY
    STOP = RESULTS / "STOP"
SPECIALTIES = json.loads(SPECIALTIES_FILE.read_text(encoding="utf-8-sig"))["specialties"]
if options.describe:
    print(json.dumps({"country": COUNTRY, "places": len(CITIES), "specialties": len(SPECIALTIES),
                      "queries": len(CITIES)*len(SPECIALTIES), "output": str(OUT_DIR), "results": str(RESULTS)}))
    raise SystemExit(0)
OUT = OUT_DIR / "all_leads.csv"
BY_SPECIALTY = OUT_DIR
DB = RESULTS / "leads.sqlite3"
RESULTS.mkdir(parents=True, exist_ok=True)
MAX_BUSINESSES = options.max_businesses
MAX_EMAILS = options.max_emails
LEAD_LIMIT = None if options.overnight or options.pilot_specialties else max(1, options.test_limit)
SPECIALTY_LIMIT_COUNT = options.pilot_specialties
EXPORT_BATCH_SIZE = 10
SCROLL_ROUNDS = 8 if COUNTRY == "scotland" else 2
USER_AGENT = "PublicBusinessContacts/1.0 (polite contact-page crawler)"
logging.basicConfig(handlers=[RotatingFileHandler(RESULTS / "fast-leads.log", maxBytes=10_000_000,
                                                   backupCount=5, encoding="utf-8")], level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

conn = sqlite3.connect(DB)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("CREATE TABLE IF NOT EXISTS queries (city TEXT, specialty TEXT, done INTEGER DEFAULT 0, PRIMARY KEY(city,specialty))")
conn.execute("CREATE TABLE IF NOT EXISTS businesses (id TEXT PRIMARY KEY, name TEXT, website TEXT, city TEXT)")
conn.execute("CREATE TABLE IF NOT EXISTS checked_businesses (id TEXT PRIMARY KEY)")
conn.execute("CREATE TABLE IF NOT EXISTS emails (email TEXT PRIMARY KEY, name TEXT, mx_ok INTEGER, source TEXT)")
conn.execute("CREATE TABLE IF NOT EXISTS email_categories (email TEXT, name TEXT, specialty TEXT, PRIMARY KEY(email,specialty))")
conn.commit()

site_sem = asyncio.Semaphore(max(1, options.site_concurrency))
domain_locks: dict[str, asyncio.Lock] = {}
domain_email_cache: dict[str, str | None] = {}
robots_cache: dict[str, RobotFileParser | None] = {}
mx_cache: dict[str, bool] = {}
email_write_lock = asyncio.Lock()
dirty_specialties: set[str] = set()
pending_export_rows = 0
http = httpx.AsyncClient(timeout=httpx.Timeout(9, connect=5), follow_redirects=True,
                         headers={"User-Agent": USER_AGENT}, max_redirects=4)


def safe_candidates(raw: str):
    raw = html.unescape(raw).replace("mailto:", " ")
    for candidate in re.findall(r"(?i)(?<![\w.+-])[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+", raw):
        candidate = candidate.strip(".,;:!?()[]{}<>\"'").lower()
        _, addr = parseaddr(candidate)
        if not is_valid_email(addr):
            continue
        local = addr.split("@", 1)[0]
        if local.startswith(("noreply", "no-reply", "donotreply", "example", "test@")):
            continue
        if any(word in addr for word in ("sentry.io", "wixpress.com", "schema.org", "example.com")):
            continue
        yield addr


def records_from_state(state):
    found = {}
    seen = set()
    seen_refs = []

    def walk(node):
        if isinstance(node, str):
            if node.startswith(")]}'"):
                try:
                    walk(json.loads(node[5:]))
                except (ValueError, TypeError):
                    pass
            return
        if not isinstance(node, list):
            if isinstance(node, dict):
                for value in node.values():
                    walk(value)
            return
        marker = id(node)
        if marker in seen:
            return
        seen.add(marker)
        seen_refs.append(node)
        if len(node) > 78 and isinstance(node[11], str) and isinstance(node[18], str):
            name = node[11].strip()
            address = node[18]
            details = node[7] if isinstance(node[7], list) else []
            website = details[0] if details and isinstance(details[0], str) else ""
            if name and website.startswith(("http://", "https://")):
                found.setdefault(name + "|" + website, {"name": name, "website": website, "address": address})
            return
        for child in node:
            walk(child)

    walk(state)
    return list(found.values())


async def public_host(host: str) -> bool:
    resolver = dns.asyncresolver.Resolver()

    async def lookup(record_type):
        try:
            answer = await resolver.resolve(host, record_type, lifetime=3)
            return [str(item) for item in answer]
        except Exception:
            return []

    answers = await asyncio.gather(lookup("A"), lookup("AAAA"))
    addresses = [address for group in answers for address in group]
    try:
        return bool(addresses) and all(ipaddress.ip_address(address).is_global for address in addresses)
    except ValueError:
        return False


async def mx_exists(domain: str) -> bool:
    if domain not in mx_cache:
        try:
            answer = await asyncio.to_thread(dns.resolver.resolve, domain, "MX", lifetime=4)
            mx_cache[domain] = bool(answer)
        except Exception:
            try:
                answer = await asyncio.to_thread(dns.resolver.resolve, domain, "A", lifetime=3)
                mx_cache[domain] = bool(answer)
            except Exception:
                mx_cache[domain] = False
    return mx_cache[domain]


async def robots_for(origin: str):
    if origin not in robots_cache:
        parser = RobotFileParser()
        try:
            response = await http.get(urljoin(origin, "/robots.txt"))
            if response.status_code < 400:
                parser.parse(response.text.splitlines())
                robots_cache[origin] = parser
            else:
                robots_cache[origin] = None
        except Exception:
            robots_cache[origin] = None
    return robots_cache[origin]


async def checked_crawl(item):
    await crawl_business(item)
    business_id = item["name"].casefold() + "|" + item["website"].casefold()
    conn.execute("INSERT OR IGNORE INTO checked_businesses(id) VALUES(?)", (business_id,))
    conn.commit()


async def crawl_business(item):
    website = item["website"]
    parsed = urlparse(website)
    host = (parsed.hostname or "").lower()
    if not host or parsed.scheme not in ("http", "https") or parsed.username or parsed.password:
        return
    domain_key = host.removeprefix("www.")
    lock = domain_locks.setdefault(domain_key, asyncio.Lock())
    async with lock:
        if domain_key in domain_email_cache:
            email = domain_email_cache[domain_key]
            if email:
                await save_email(email, item["name"], item["website"], item["specialty"])
            return
        if not await public_host(host):
            domain_email_cache[domain_key] = None
            return
        origin = f"{parsed.scheme}://{parsed.netloc}"
        robots = await robots_for(origin)
        paths = [website]
        contact_paths = ("/kontaktai", "/apie-mus", "/contact", "/contact-us", "/about") if COUNTRY == "lithuania" else ("/contact", "/contact-us", "/about", "/about-us")
        for page in contact_paths:
            paths.append(urljoin(origin, page))
        discovered = None
        async with site_sem:
            for url in paths:
                if robots and not robots.can_fetch(USER_AGENT, url):
                    continue
                try:
                    response = await http.get(url)
                    if response.status_code >= 400 or "html" not in response.headers.get("content-type", "").lower():
                        continue
                    page_host = (urlparse(str(response.url)).hostname or "").lower()
                    if not await public_host(page_host):
                        continue
                    soup = BeautifulSoup(response.text[:1_000_000], "html.parser")
                    for link in soup.select('a[href^="mailto:"]'):
                        discovered = next(safe_candidates(link.get("href", "")), None)
                        if discovered:
                            break
                    if not discovered:
                        for node in soup(["script", "style", "noscript", "svg"]):
                            node.decompose()
                        discovered = next(safe_candidates(soup.get_text(" ", strip=True)), None)
                    if discovered:
                        break
                except Exception:
                    continue
        domain_email_cache[domain_key] = discovered
        if discovered:
            await save_email(discovered, item["name"], str(response.url), item["specialty"])


async def save_email(email, name, source, specialty):
    domain = email.rsplit("@", 1)[-1]
    if not await mx_exists(domain):
        return
    global pending_export_rows
    async with email_write_lock:
        if LEAD_LIMIT is not None and conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0] >= LEAD_LIMIT:
            return
        email_cursor = conn.execute("INSERT OR IGNORE INTO emails(email,name,mx_ok,source) VALUES(?,?,1,?)", (email, name, source))
        category_cursor = conn.execute("INSERT OR IGNORE INTO email_categories(email,name,specialty) VALUES(?,?,?)", (email, name, specialty))
        if email_cursor.rowcount or category_cursor.rowcount:
            conn.commit()
            if category_cursor.rowcount:
                dirty_specialties.add(specialty)
            pending_export_rows += 1
            if pending_export_rows >= EXPORT_BATCH_SIZE:
                export_csv(sorted(dirty_specialties))
                dirty_specialties.clear()
                pending_export_rows = 0


def export_csv(changed_specialties=None, initialize_categories=False):
    rows = conn.execute("SELECT name,email FROM emails ORDER BY name COLLATE NOCASE,email").fetchall()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    BY_SPECIALTY.mkdir(parents=True, exist_ok=True)
    temp = OUT.with_suffix(".csv.tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Pavadinimas", "El. pa" + chr(0x0161) + "tas"])
        writer.writerows(rows)
    temp.replace(OUT)
    grouped = conn.execute("SELECT specialty,name,email FROM email_categories ORDER BY specialty COLLATE NOCASE,name COLLATE NOCASE,email").fetchall()
    groups = {}
    for specialty, name, email in grouped:
        groups.setdefault(specialty, []).append((name, email))
    if initialize_categories:
        specialties = sorted(groups, key=str.casefold)
    else:
        specialties = list(changed_specialties or [])
    for specialty in specialties:
        group = groups.get(specialty, [])
        slug = re.sub(r"[^a-z0-9]+", "-", __import__("unicodedata").normalize("NFKD", specialty.casefold()).encode("ascii", "ignore").decode()).strip("-") or "specialybe"
        path = BY_SPECIALTY / f"{slug}.csv"
        tmp = path.with_suffix(".csv.tmp")
        with tmp.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Pavadinimas", "El. pa" + chr(0x0161) + "tas"])
            writer.writerows(group)
        tmp.replace(path)
    return len(rows)


async def maps_records(page, city, specialty):
    from urllib.parse import quote_plus
    place = city["query"] if isinstance(city, dict) else city
    query = quote_plus(f"{specialty} in {place}, {PROFILE['country']}")
    location = f"/@{city['latitude']},{city['longitude']},13z" if isinstance(city, dict) else ""
    url = f"https://www.google.com/maps/search/{query}{location}?hl=en&gl={PROFILE['gl']}"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        feed = page.locator('div[role="feed"]').first
        await feed.wait_for(state="visible", timeout=8000)
        results = {}
        for _ in range(SCROLL_ROUNDS + 1):
            state = await page.evaluate("window.APP_INITIALIZATION_STATE")
            for item in records_from_state(state):
                results.setdefault(item["name"] + "|" + item["website"], item)
            if len(results) >= 90:
                break
            await feed.evaluate("el => el.scrollTop = el.scrollHeight")
            await page.wait_for_timeout(950)
        return list(results.values())
    except Exception as exc:
        logging.info("Maps query failed: %s / %s: %s", city, specialty, str(exc)[:180])
        return None


async def run():
    cities = CITIES
    specialties = SPECIALTIES
    business_count = conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0]
    email_count = export_csv(initialize_categories=True)
    browser = BrowserManager(headless=True, locale=PROFILE["locale"], timezone_id=PROFILE["timezone"])
    page = await browser.start()
    pending_sites: set[asyncio.Task] = set()
    logging.info("START cities=%d specialties=%d businesses=%d emails=%d", len(cities), len(specialties), business_count, email_count)
    try:
        failed_streak = 0
        selected_specialties = specialties[:SPECIALTY_LIMIT_COUNT] if SPECIALTY_LIMIT_COUNT is not None else specialties
        for specialty in selected_specialties:
            for place in cities:
                city = str(place["geoname_id"]) if isinstance(place, dict) else place
                if STOP.exists():
                    logging.info("Stopped at operator request")
                    return
                done = conn.execute("SELECT done FROM queries WHERE city=? AND specialty=?", (city, specialty)).fetchone()
                if done and done[0]:
                    continue
                found = await maps_records(page, place, specialty)
                if found is None:
                    logging.warning("Retrying incomplete Maps search: %s | %s", city, specialty)
                    await page.wait_for_timeout(2000)
                    found = await maps_records(page, place, specialty)
                    if found is None:
                        failed_streak += 1
                        logging.error("Skipping failed search for now; it remains resumable: %s | %s", city, specialty)
                        if failed_streak >= 4:
                            logging.warning("Four Maps searches failed in a row; cooling down briefly before continuing.")
                            await page.wait_for_timeout(10000)
                            failed_streak = 0
                        continue
                failed_streak = 0
                for item in found:
                    if LEAD_LIMIT is not None and conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0] >= LEAD_LIMIT:
                        break
                    item["specialty"] = specialty
                    if conn.execute("SELECT 1 FROM checked_businesses WHERE id=?", (item["name"].casefold()+"|"+item["website"].casefold(),)).fetchone():
                        continue
                    conn.execute("INSERT OR IGNORE INTO businesses(id,name,website,city) VALUES(?,?,?,?)", (item["name"].casefold()+"|"+item["website"].casefold(), item["name"], item["website"], city))
                    conn.commit()
                    pending_sites.add(asyncio.create_task(checked_crawl(item)))
                    if len(pending_sites) >= max(8, options.site_concurrency * 3):
                        done, pending_sites = await asyncio.wait(pending_sites, return_when=asyncio.FIRST_COMPLETED)
                        for task in done:
                            task.result()
                if pending_sites:
                    await asyncio.gather(*pending_sites)
                    pending_sites.clear()
                conn.execute("INSERT OR REPLACE INTO queries(city,specialty,done) VALUES(?,?,1)", (city,specialty))
                conn.commit()
                business_count = conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0]
                email_count = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
                logging.info("%s | %s | %d map businesses | %d DNS-checked emails", place["query"] if isinstance(place, dict) else city, specialty, business_count, email_count)
                if (LEAD_LIMIT is not None and email_count >= LEAD_LIMIT) or business_count >= MAX_BUSINESSES or email_count >= MAX_EMAILS:
                    logging.info("Requested lead limit reached; stopping after the test batch.")
                    return
        if SPECIALTY_LIMIT_COUNT is None:
            completed = conn.execute("SELECT COUNT(*) FROM queries WHERE done=1").fetchone()[0]
            if completed < len(cities) * len(specialties):
                raise RuntimeError("Incomplete searches remain; restart to retry them")
            logging.info("All city/specialty searches complete")
        else:
            logging.info("Requested specialty test complete: %d specialties", len(selected_specialties))
    finally:
        # Let already collected public sites finish, then make final atomic CSV.
        if pending_sites:
            try:
                await asyncio.wait_for(asyncio.gather(*pending_sites, return_exceptions=True), timeout=75)
            except asyncio.TimeoutError:
                logging.warning("Some slow site checks exceeded 75 seconds; cancelling them and saving completed contacts.")
                for task in pending_sites:
                    task.cancel()
                await asyncio.gather(*pending_sites, return_exceptions=True)
        export_csv(sorted(dirty_specialties), initialize_categories=True)
        await http.aclose()
        await browser.close()
        conn.close()


if __name__ == "__main__":
    def request_stop(signum, frame):
        STOP.touch()
    signal.signal(signal.SIGTERM, request_stop)
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print(f"Stopped. Leads saved to: {OUT}")
