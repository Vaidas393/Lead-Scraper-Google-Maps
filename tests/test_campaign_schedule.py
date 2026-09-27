import json
import sqlite3
from pathlib import Path
from campaign_schedule import scheduled_queries, campaign_deadline


def test_month_plan_coverage_and_balanced_order():
    root=Path(__file__).resolve().parents[1]
    plan=json.loads((root/'campaigns/scotland-month.json').read_text(encoding='utf8'))
    full=json.loads((root/'campaigns/scotland.json').read_text(encoding='utf8'))['cities']
    selected={p['geoname_id']:p for p in full if p['geoname_id'] in plan['city_ids']}
    assert len(selected)==160
    assert len({p['query'].split(', ',1)[-1] for p in selected.values()})==32
    assert all(p['feature_code']!='PPLX' for p in selected.values())
    schedule=list(scheduled_queries(plan['city_ids'],plan['specialties'],plan['phase_ends']))
    assert len(schedule)==len(set(schedule))==23680
    assert len({s for c,s in schedule[:160]})==148
    assert len({c for c,s in schedule[:160]})==40
    assert {c for c,s in schedule[:40*148]}==set(plan['city_ids'][:40])


def test_deadline_survives_restart(tmp_path):
    path=tmp_path/'progress.db'
    conn=sqlite3.connect(path)
    end=campaign_deadline(conn,'month',30,now=100)
    conn.close()
    conn=sqlite3.connect(path)
    assert campaign_deadline(conn,'month',30,now=200000)==end==100+30*86400
    conn.close()
