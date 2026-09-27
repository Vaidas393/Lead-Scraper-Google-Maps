"""Country CSV exports and a process lock released by the OS after a crash."""
import csv
import os
import re
import unicodedata
from pathlib import Path


class CampaignLock:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open('a+b')
        self.handle.seek(0)
        if os.fstat(self.handle.fileno()).st_size == 0:
            self.handle.write(b'0')
            self.handle.flush()
        self.handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.handle.close()
            raise RuntimeError(f'Campaign already running: {self.path}') from None

    def close(self):
        if not self.handle.closed:
            self.handle.close()


def atomic_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.csv.tmp')
    with tmp.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['Pavadinimas', 'El. pa\u0161tas'])
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def export_country(conn, directory, specialties=None):
    directory = Path(directory)
    rows = conn.execute('SELECT name,email FROM emails ORDER BY name COLLATE NOCASE,email').fetchall()
    atomic_csv(directory / 'all_leads.csv', rows)
    if specialties is None:
        specialties = [r[0] for r in conn.execute('SELECT DISTINCT specialty FROM email_categories')]
    for specialty in specialties:
        slug = re.sub(r'[^a-z0-9]+', '-', unicodedata.normalize('NFKD', specialty.casefold()).encode('ascii', 'ignore').decode()).strip('-') or 'specialybe'
        group = conn.execute('SELECT name,email FROM email_categories WHERE specialty=? ORDER BY name COLLATE NOCASE,email', (specialty,)).fetchall()
        atomic_csv(directory / 'categories' / f'{slug}.csv', group)
    return len(rows)

