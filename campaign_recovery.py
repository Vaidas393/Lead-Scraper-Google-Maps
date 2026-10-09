"""Distinguish single-place responses from actual search failures."""
from scraper.extract import extract_detail


async def without_feed(page):
    text = (await page.locator('body').inner_text(timeout=5000)).lower()
    if '/sorry/' in page.url or any(s in text for s in ('unusual traffic', 'verify you are human', 'before you continue to google')):
        raise RuntimeError('Maps access/consent page; query remains pending')
    if await page.locator('div[role="main"] h1').count() and await page.locator('button[data-item-id="address"], button[data-item-id^="phone"], a[data-item-id="authority"]').count():
        detail = await extract_detail(page)
        if not detail.get('name'):
            raise RuntimeError('Single place did not expose a name')
        website = detail.get('websiteUrl') or ''
        if website.startswith(('https://', 'http://')):
            return [{'name': detail['name'], 'website': website, 'address': detail.get('address') or ''}]
        return []  # Valid listing without a public website to crawl.
    if "google maps can't find" in text or 'no results found' in text:
        return []
    raise RuntimeError('Unrecognized Maps response: ' + text[:250])


def init_retries(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS query_retries(city TEXT,specialty TEXT,attempts INTEGER,next_retry REAL,PRIMARY KEY(city,specialty))')
    conn.commit()


def defer_query(conn, city, specialty, now):
    row=conn.execute('SELECT attempts FROM query_retries WHERE city=? AND specialty=?',(city,specialty)).fetchone()
    attempts=(row[0] if row else 0)+1
    delay=min(86400, 900 * 2**min(attempts-1,7))
    conn.execute('INSERT OR REPLACE INTO query_retries VALUES(?,?,?,?)',(city,specialty,attempts,now+delay))
    conn.commit()
    return delay


def retry_ready(conn, city, specialty, now):
    row=conn.execute('SELECT next_retry FROM query_retries WHERE city=? AND specialty=?',(city,specialty)).fetchone()
    return row is None or row[0]<=now
