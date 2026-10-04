"""Exercise different goals through one registry. --live uses actual configured API; never falls back."""
import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from core import Engine, Store


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--live',action='store_true',help='Require an actual configured model API; no scripted fallback.')
    parser.add_argument('--report',default='artifacts/goal-verification.json')
    args=parser.parse_args()
    if args.live and not os.getenv('OPENAI_API_KEY'):
        raise SystemExit('Live execution unavailable: configure OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL in .env. No model calls were made.')
    goals=[
        ('Handle open billing questions, draft replies using our policies, and escalate refund requests.','process',[1,2,5],False),
        ('Handle ticket 6 and remember its explicit reply preference.','process',[6],False),
        ("Review ticket 7, retrieve the customer's preferences, and draft a reply without changing its status.",'draft_only',[7],False),
        ('Check whether ticket 2 was resolved correctly and report any missing evidence.','audit',[2],False),
        ('Handle ticket 4 and draft export guidance using our company policies.','process',[4],True),
    ]
    report={'verified_at_utc':datetime.now(timezone.utc).isoformat(),'mode':'Live LLM mode' if args.live else 'Scripted demo mode',
            'model':os.getenv('OPENAI_MODEL','gpt-4.1-mini') if args.live else None,
            'live_llm_verified':False,'autonomy_claim':False,'goals':[]}
    with tempfile.TemporaryDirectory(prefix='opspilot-goals-') as folder:
        store=Store(Path(folder)/'fictional.sqlite3');engine=Engine(store,scripted=not args.live)
        for index,(task,operation,ids,failure) in enumerate(goals):
            before={tid:store.ticket(tid)['status'] for tid in ids}
            run,_=store.start_run(task,f'goal-verification-{index}',engine.mode)
            engine.run(run['id'],task,failure,operation,ids)
            actual=store.rows('SELECT * FROM runs WHERE id=?',(run['id'],))[0]
            verifications=store.rows('SELECT * FROM verifications WHERE run_id=?',(run['id'],))
            outcomes=store.rows('SELECT * FROM outcomes WHERE run_id=?',(run['id'],))
            entry={'goal':task,'operation':operation,'ticket_ids':ids,'mode':engine.mode,'model':actual['model'],'run_status':actual['status'],
                   'status_before':before,'status_after':{tid:store.ticket(tid)['status'] for tid in ids},'outcomes':outcomes,
                   'verification':verifications,'tool_events':store.rows('SELECT * FROM events WHERE run_id=? ORDER BY id',(run['id'],))}
            report['goals'].append(entry)
            print(json.dumps({'goal':task,'mode':engine.mode,'run_status':actual['status'],'outcomes':[o['status'] for o in outcomes]}))
        reports_ok=all(g['run_status'] in ['completed','awaiting_human'] and all(o['status']!='failed' for o in g['outcomes']) for g in report['goals'])
        billing,draft_only,audit,retry=report['goals'][0],report['goals'][2],report['goals'][3],report['goals'][4]
        refunds_pending=store.ticket(2)['status']=='needs_review' and store.ticket(5)['status']=='needs_review' and not store.rows('SELECT * FROM crm_actions')
        unchanged=draft_only['status_before']==draft_only['status_after']
        memory_events=[json.loads(e['result']) for e in draft_only['tool_events'] if e['tool']=='get_customer' and not e['error']]
        memory_reused=bool(memory_events and any(p['value']=='concise' and p['source_ticket']==6 for p in memory_events[0]['preferences']))
        audit_findings=any(json.loads(v['missing']) for v in audit['verification'] if v['outcome']=='audit_verified')
        recovered=any(e['attempt']==1 and e['error'] for e in retry['tool_events']) and any(e['attempt']==2 and not e['error'] for e in retry['tool_events'])
        before_counts=(len(store.rows('SELECT * FROM drafts')),len(store.rows('SELECT * FROM reviews')))
        run,_=store.start_run('Rerun previously processed billing tickets','rerun-goal',engine.mode)
        engine.run(run['id'],'Rerun previously processed billing tickets',False,'process',[1,2,5])
        duplicate_safe=before_counts==(len(store.rows('SELECT * FROM drafts')),len(store.rows('SELECT * FROM reviews')))
        report['checks']={'all_scoped_goals_verified':reports_ok,'refunds_awaiting_human_not_completed':refunds_pending,'draft_only_status_unchanged':unchanged,
                          'customer_memory_observed':memory_reused,'audit_reports_missing_resolution_evidence':audit_findings,'transient_failure_recovered':recovered,'rerun_did_not_duplicate_side_effects':duplicate_safe}
        report['verified']=all(report['checks'].values())
        report['live_llm_verified']=args.live and report['verified']
        report['autonomy_claim']=report['live_llm_verified']
    path=Path(args.report);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'mode':report['mode'],'verified':report['verified'],'live_llm_verified':report['live_llm_verified'],'checks':report['checks']},indent=2))
    if not report['verified']:raise SystemExit(1)

if __name__=='__main__':main()
