from pathlib import Path
import argparse
import json
from datetime import datetime, timezone
import time
import urllib.request

BASE='http://127.0.0.1:8765'
TASK='Process open tickets, look up each customer, draft appropriate replies, update the CRM, and escalate refunds or unclear cases.'

def api(path,data=None):
    req=urllib.request.Request(BASE+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=10) as res:
        return json.load(res)


def main():
    global BASE
    parser=argparse.ArgumentParser(description='Reset and verify only the fictional local OpsPilot scripted demo.')
    parser.add_argument('--base-url',default=BASE)
    parser.add_argument('--report',default='artifacts/verification.json')
    args=parser.parse_args()
    BASE=args.base_url.rstrip('/')
    if not api('/api/state')['scripted']:
        raise SystemExit('This verifier requires Scripted demo mode; it did not reset data or invoke the live provider.')
    # This command is explicitly a reset-and-verify local demo command.
    api('/api/reset',{})
    payload={'task':TASK,'request_key':'verification-demo-001','demo_failure':True}
    run=api('/api/runs',payload)
    for _ in range(100):
        state=api('/api/state')
        if state['runs'][0]['status']!='running':
            break
        time.sleep(.2)
    assert state['scripted'], 'This verification is intended for explicitly scripted demo mode.'
    assert state['metrics']=={'processed':8,'escalated':3,'failed':0,'retries':1},state['metrics']
    assert all(t['status'] in ['drafted','needs_review'] for t in state['tickets'])
    repeated=api('/api/runs',payload)
    assert repeated['duplicate'] and repeated['run']['id']==run['run']['id']
    injection=api('/api/tickets/5')
    assert injection['reviews'][0]['status']=='pending'
    assert injection['ticket']['status']=='needs_review'
    assert 'Approval is pending' in injection['drafts'][0]['body']
    later=api('/api/tickets/7')
    assert later['preferences'][0]['value']=='concise'
    assert 'No changes made.' in later['drafts'][0]['body']
    refund=api('/api/tickets/2')
    rid=refund['reviews'][0]['id']
    assert api('/api/reviews/'+str(rid),{'decision':'approved'})['simulated_only']
    assert api('/api/reviews/'+str(rid),{'decision':'approved'})['duplicate']
    assert len(api('/api/tickets/2')['crm_actions'])==1
    report={'verified_at_utc':datetime.now(timezone.utc).isoformat(),'verified':True,'mode':state['mode'],'live_llm_verified':False,'metrics':state['metrics'],'run_status':state['runs'][0]['status'],'completed_work':sum(t['status']=='drafted' for t in state['tickets']),'awaiting_human':sum(t['status']=='needs_review' for t in state['tickets']),'run_id':run['run']['id'],
            'checks':['8 seeded tickets processed and independently verified; refunds awaiting human approval','transient failure recovered','duplicate HTTP request reused the same run','injection ticket held for human approval','customer preference reused','human refund approval recorded one simulated CRM action'],
            'pending_reviews_after_demo':2}
    report_path=Path(args.report)
    report_path.parent.mkdir(parents=True,exist_ok=True)
    report_path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
