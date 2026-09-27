"""A bounded, geographically varied Scotland campaign."""
import time


def scheduled_queries(cities, specialties, phase_ends=None):
    if not phase_ends:
        for specialty in specialties:
            for city in cities:
                yield city, specialty
        return
    start = 0
    for end in phase_ends:
        batch = cities[start:end]
        for turn in range(len(specialties)):
            for index, city in enumerate(batch):
                yield city, specialties[(turn + index * max(1, (len(specialties) + len(batch) - 1) // len(batch))) % len(specialties)]
        start = end


def campaign_deadline(conn, plan_name, days, now=None):
    now = time.time() if now is None else now
    conn.execute('CREATE TABLE IF NOT EXISTS campaign_deadlines (plan TEXT PRIMARY KEY, started REAL, deadline REAL)')
    conn.execute('INSERT OR IGNORE INTO campaign_deadlines VALUES(?,?,?)', (plan_name, now, now + days * 86400))
    conn.commit()
    return conn.execute('SELECT deadline FROM campaign_deadlines WHERE plan=?', (plan_name,)).fetchone()[0]

