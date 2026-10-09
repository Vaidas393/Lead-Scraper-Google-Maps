import sqlite3
import pytest
import campaign_recovery as recovery

class Locator:
    def __init__(self, text='', count=0): self.text,self.n=text,count
    async def inner_text(self, **kwargs): return self.text
    async def count(self): return self.n
class Page:
    url='https://www.google.com/maps/search/example'
    def __init__(self,text,detail=False): self.text,self.detail=text,detail
    def locator(self,selector): return Locator(self.text, int(self.detail))

@pytest.mark.asyncio
async def test_single_place_with_and_without_website(monkeypatch):
    detail={'name':'Business','websiteUrl':'https://business.test','address':'Address'}
    async def extract(page): return detail
    monkeypatch.setattr(recovery,'extract_detail',extract)
    assert (await recovery.without_feed(Page('Overview',True)))[0]['website']=='https://business.test'
    detail['websiteUrl']=None
    assert await recovery.without_feed(Page('Overview',True))==[]

@pytest.mark.asyncio
async def test_empty_and_blocked_are_not_confused():
    assert await recovery.without_feed(Page("Google Maps can't find this place"))==[]
    for text in ['unusual traffic','Unknown page','before you continue to Google']:
        with pytest.raises(RuntimeError): await recovery.without_feed(Page(text))

def test_retry_deferral_survives_restart_and_does_not_block_other_queries(tmp_path):
    path=tmp_path/'state.db'
    conn=sqlite3.connect(path); recovery.init_retries(conn)
    assert recovery.defer_query(conn,'city','failed',100)==900
    conn.close(); conn=sqlite3.connect(path)
    assert not recovery.retry_ready(conn,'city','failed',101)
    assert recovery.retry_ready(conn,'city','other',101)
    assert recovery.retry_ready(conn,'city','failed',1000)
    assert recovery.defer_query(conn,'city','failed',1000)==1800
    conn.close()
