import csv
import sqlite3
import subprocess
import sys
from pathlib import Path
import pytest
from campaign_storage import CampaignLock, export_country


def database(path):
    conn = sqlite3.connect(path)
    conn.executescript('CREATE TABLE emails(email TEXT PRIMARY KEY,name TEXT); CREATE TABLE email_categories(email TEXT,name TEXT,specialty TEXT,PRIMARY KEY(email,specialty));')
    conn.execute('INSERT INTO emails VALUES(?,?)', ('contact@business.lt','Verslas'))
    conn.executemany('INSERT INTO email_categories VALUES(?,?,?)', [('contact@business.lt','Verslas','kirpykla'),('contact@business.lt','Verslas','grožio salonas')])
    conn.commit()
    return conn


def read(path):
    with path.open(encoding='utf-8-sig',newline='') as handle:
        return list(csv.reader(handle))


def test_export_rebuild_after_interrupted_write_and_multiple_categories(tmp_path):
    db = tmp_path/'progress.db'
    conn = database(db)
    directory=tmp_path/'leads'/'lithuania'
    export_country(conn,directory)
    conn.close()
    (directory/'all_leads.csv.tmp').write_text('interrupted output')
    conn=sqlite3.connect(db)
    export_country(conn,directory)
    assert len(read(directory/'all_leads.csv'))==2
    assert read(directory/'categories'/'kirpykla.csv')==read(directory/'categories'/'grozio-salonas.csv')
    assert not (directory/'all_leads.csv.tmp').exists()
    assert not (tmp_path/'leads'/'scotland').exists()
    conn.close()


def test_failed_replace_preserves_previous_csv(tmp_path,monkeypatch):
    conn=database(tmp_path/'progress.db')
    export_country(conn,tmp_path/'country')
    path=tmp_path/'country'/'all_leads.csv'
    previous=path.read_bytes()
    conn.execute('INSERT INTO emails VALUES(?,?)',('new@business.lt','New'))
    def fail(*args):
        raise OSError('simulated disk failure')
    monkeypatch.setattr(Path,'replace',fail)
    with pytest.raises(OSError):
        export_country(conn,tmp_path/'country')
    assert path.read_bytes()==previous
    conn.close()


def test_lock_released_after_process_crash(tmp_path):
    lock=tmp_path/'campaign.lock'
    code='from campaign_storage import CampaignLock; import sys,time; lock=CampaignLock(sys.argv[1]); print("locked",flush=True); time.sleep(60)'
    child=subprocess.Popen([sys.executable,'-c',code,str(lock)],stdout=subprocess.PIPE,text=True)
    try:
        assert child.stdout.readline().strip()=='locked'
        with pytest.raises(RuntimeError,match='already running'):
            CampaignLock(lock)
        child.kill()
        child.wait(timeout=10)
        import time
        for attempt in range(20):
            try:
                resumed=CampaignLock(lock)
                break
            except RuntimeError:
                if attempt == 19:
                    raise
                time.sleep(0.1)
        resumed.close()
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)

@pytest.mark.asyncio
async def test_resume_unfinished_query_without_losing_category(tmp_path,monkeypatch):
    import runpy
    import shutil
    root=Path(__file__).resolve().parents[1]
    repo=tmp_path/'repo'
    repo.mkdir()
    for name in ('fast_leads.py','cities.json','specialties.json'):
        shutil.copy2(root/name,repo/name)
    monkeypatch.setattr(sys,'argv',['fast_leads.py','--overnight'])
    class Browser:
        def __init__(self,**kwargs): pass
        async def start(self): return object()
        async def close(self): pass
    async def maps(*args):
        return [{'name':name,'website':f'https://{name}.test'} for name in ('first','second')]
    async def yes(*args): return True
    calls=[]
    def load(fail):
        module=runpy.run_path(str(repo/'fast_leads.py'),run_name='campaign_test')
        state=module['run'].__globals__
        state.update(CITIES=['City'],SPECIALTIES=['hairdresser','beauty salon'],BrowserManager=Browser,maps_records=maps,mx_exists=yes)
        async def crawl(item):
            calls.append((item['name'],item['specialty']))
            if fail and item['name']=='second':
                raise RuntimeError('simulated process failure')
            await state['save_email'](item['name']+'@business.test',item['name'],item['website'],item['specialty'])
        state['crawl_business']=crawl
        return state
    first=load(True)
    try:
        with pytest.raises(RuntimeError,match='simulated process failure'):
            await first['run']()
    finally:
        first['campaign_lock'].close()
    check=sqlite3.connect(repo/'results/leads.sqlite3')
    assert check.execute('SELECT COUNT(*) FROM queries WHERE done=1').fetchone()[0]==0
    assert check.execute('SELECT COUNT(*) FROM emails').fetchone()[0]==1
    check.close()
    calls.clear()
    resumed=load(False)
    try:
        await resumed['run']()
    finally:
        resumed['campaign_lock'].close()
    assert ('first','hairdresser') not in calls
    assert ('first','beauty salon') in calls
    check=sqlite3.connect(repo/'results/leads.sqlite3')
    assert check.execute('SELECT COUNT(*) FROM emails').fetchone()[0]==2
    assert check.execute('SELECT COUNT(*) FROM email_categories').fetchone()[0]==4
    assert check.execute('SELECT COUNT(*) FROM queries WHERE done=1').fetchone()[0]==2
    check.close()
