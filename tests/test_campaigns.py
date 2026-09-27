from pathlib import Path
import hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]

def describe(country):
    result=subprocess.run([sys.executable,str(ROOT/'fast_leads.py'),'--country',country,'--describe'],capture_output=True,text=True,check=True)
    return json.loads(result.stdout)

def test_country_storage_isolation():
    lt,sc=describe('lithuania'),describe('scotland')
    assert lt['places']==103 and lt['specialties']==238
    assert lt['output']!=sc['output'] and lt['results']!=sc['results']
    assert sc['specialties']==238

def test_scotland_coverage_and_unique_ids():
    profile=json.loads((ROOT/'campaigns/scotland.json').read_text(encoding='utf8'))
    places=profile['cities']
    assert len(places)>6000
    assert len({p['geoname_id'] for p in places})==len(places)
    assert {'Glasgow','Edinburgh','Aberdeen','Dundee','Inverness','Stirling','Perth','Dunfermline'} <= {p['name'] for p in places}
    assert all(54.5<p['latitude']<61 and -9<p['longitude']<0 for p in places)
