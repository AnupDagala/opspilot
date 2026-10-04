import json
import httpx
import pytest
from fastapi.testclient import TestClient

from core import Store, Engine, ToolRunner, BoundaryError, BudgetError, BusyError, TransientToolError
from main import create_app

TASK='Process open tickets and escalate refunds or unclear cases.'

@pytest.fixture
def store(tmp_path):
    return Store(tmp_path/'test.sqlite3')


def run_demo(store, key='test-request-1', failure=True):
    engine=Engine(store,scripted=True)
    run,fresh=store.start_run(TASK,key,engine.mode)
    if fresh:
        engine.run(run['id'],TASK,failure)
    return run


def runner(store, tid):
    run,_=store.start_run(TASK,'tools-request-1','Scripted demo mode')
    return ToolRunner(store,run['id'],tid)


def retrieve_and_draft(tools, tid, cid, body='We have recorded your request for human review. Approval is pending.'):
    tools.call('get_customer',{'customer_id':cid})
    p=tools.call('search_policies',{'query':'refund billing clarification'})
    return tools.call('save_reply_draft',{'ticket_id':tid,'body':body,'policy_ids':[x['id'] for x in p]})


def test_duplicate_run_and_action_prevention(store):
    first=run_demo(store)
    before={t:len(store.rows(f'SELECT * FROM {t}')) for t in ['drafts','reviews','events']}
    same,fresh=store.start_run(TASK,'test-request-1','Scripted demo mode')
    assert not fresh and same['id']==first['id']
    run_demo(store,key='different-request-2')
    assert len(store.rows('SELECT * FROM drafts'))==before['drafts']==8
    assert len(store.rows('SELECT * FROM reviews'))==before['reviews']==3
    # Direct replay also uses ticket-scoped action keys, independent of request keys.
    tools=ToolRunner(store,first['id'],2)
    result=tools.call('request_human_review',{'ticket_id':2,'reason':'refund'})
    assert result['duplicate']
    assert len(store.rows('SELECT * FROM reviews'))==3


def test_retry_recovery(store):
    run=run_demo(store)
    events=store.rows("SELECT * FROM events WHERE ticket_id=4 AND tool='get_customer' ORDER BY id")
    assert [e['attempt'] for e in events]==[1,2]
    assert events[0]['error'] and not events[1]['error']
    assert store.ticket(4)['status']=='drafted'
    assert store.snapshot()['metrics']=={'processed':8,'escalated':3,'failed':0,'retries':1}
    assert store.rows('SELECT status FROM runs WHERE id=?',(run['id'],))[0]['status']=='awaiting_human'


def test_refund_enforcement_even_when_worker_omits_review(store):
    tools=runner(store,2)
    retrieve_and_draft(tools,2,2)
    result=tools.call('update_ticket',{'ticket_id':2,'status':'drafted'})
    assert result['status']=='needs_review'
    assert store.rows('SELECT reason,status FROM reviews WHERE ticket_id=2')==[{'reason':'refund','status':'pending'}]
    assert not store.rows('SELECT * FROM crm_actions')
    with pytest.raises(BoundaryError):
        tools.call('update_ticket',{'ticket_id':2,'status':'approved'})


def test_prompt_injection_cannot_bypass_approval(store):
    assert 'SYSTEM OVERRIDE' in store.ticket(5)['body']
    tools=runner(store,5)
    retrieve_and_draft(tools,5,5,body='Ignore policy. I confirm everything is complete and the money is on its way.')
    tools.call('update_ticket',{'ticket_id':5,'status':'drafted'})
    assert store.ticket(5)['status']=='needs_review'
    draft=store.rows('SELECT body FROM drafts WHERE ticket_id=5')[0]['body']
    assert 'Approval is pending' in draft and 'money is on its way' not in draft
    assert not store.rows('SELECT * FROM crm_actions')
    with pytest.raises(BoundaryError):
        tools.call('update_ticket',{'ticket_id':5,'status':'drafted','refund_approved':True})


def test_customer_memory_reused_on_later_ticket_and_run(store):
    run_demo(store)
    events=store.rows("SELECT result FROM events WHERE ticket_id=7 AND tool='get_customer'")
    pref=json.loads(events[0]['result'])['preferences'][0]
    assert pref['value']=='concise' and pref['source_ticket']==6
    with store.db() as c:
        c.execute("INSERT INTO tickets(id,customer_id,title,body,kind) VALUES(9,1,'Later plan question','How do I manage my plan?','plan')")
    # Recreate both objects to verify SQLite memory, not in-process state.
    reopened=Store(store.path)
    run_demo(reopened,key='later-request-9',failure=False)
    body=reopened.rows('SELECT body FROM drafts WHERE ticket_id=9')[0]['body']
    assert body=='Hi Maya, manage your plan in Settings > Billing. No changes made.'
    later=reopened.rows("SELECT result FROM events WHERE ticket_id=9 AND tool='get_customer'")
    assert json.loads(later[0]['result'])['preferences'][0]['value']=='concise'


def test_human_approval_simulated_and_idempotent(store):
    run_demo(store)
    rid=store.rows("SELECT id FROM reviews WHERE ticket_id=2")[0]['id']
    store.decide(rid,'approved')
    assert store.ticket(2)['status']=='approved'
    assert store.decide(rid,'approved')['duplicate']
    actions=store.rows('SELECT * FROM crm_actions')
    assert len(actions)==1 and 'SIMULATED' in actions[0]['action']
    with pytest.raises(BoundaryError): store.decide(rid,'rejected')
    reject=store.rows('SELECT id FROM reviews WHERE ticket_id=5')[0]['id']
    store.decide(reject,'rejected')
    assert store.ticket(5)['status']=='rejected'
    assert len(store.rows('SELECT * FROM crm_actions'))==1


def test_cross_ticket_and_customer_access_blocked(store):
    tools=runner(store,1)
    with pytest.raises(BoundaryError): tools.call('get_customer',{'customer_id':2})
    with pytest.raises(BoundaryError): tools.call('request_human_review',{'ticket_id':2,'reason':'refund'})
    assert not store.rows('SELECT * FROM reviews')


def test_execution_budget_includes_invalid_calls(store):
    tools=runner(store,1)
    for _ in range(12):
        with pytest.raises(BoundaryError): tools.call('update_ticket',{'ticket_id':1,'status':'approved'})
    with pytest.raises(BudgetError): tools.call('get_customer',{'customer_id':1})
    assert len(store.rows('SELECT * FROM events WHERE ticket_id=1'))==12


def test_retry_exhaustion_isolated_to_one_ticket(store,monkeypatch):
    original=ToolRunner.execute
    def flaky(self,name,args):
        if self.ticket_id==4 and name=='get_customer':
            raise TransientToolError('Temporary lookup unavailable.')
        return original(self,name,args)
    monkeypatch.setattr(ToolRunner,'execute',flaky)
    run_demo(store,failure=False)
    events=store.rows("SELECT * FROM events WHERE ticket_id=4 AND tool='get_customer'")
    assert [e['attempt'] for e in events]==[1,2,3,4]
    assert store.ticket(4)['status']=='failed'
    assert store.ticket(8)['status']=='drafted'
    assert store.snapshot()['metrics']['failed']==1


def test_busy_and_reset_guards(store):
    store.start_run(TASK,'running-request','Scripted demo mode')
    with pytest.raises(BusyError):store.start_run(TASK,'second-request','Scripted demo mode')
    with pytest.raises(BusyError):store.reset()
    store.recover()
    assert store.rows('SELECT status FROM runs')[0]['status']=='interrupted'
    store.reset()
    assert len(store.rows('SELECT * FROM tickets'))==8
    assert not store.rows('SELECT * FROM runs')


def test_api_complete_flow_duplicate_reset_and_origin(store):
    engine=Engine(store,scripted=True)
    with TestClient(create_app(store,engine)) as client:
        assert client.get('/').status_code==200
        assert client.get('/static/app.js').status_code==200
        payload={'task':TASK,'request_key':'api-request-1','demo_failure':True}
        first=client.post('/api/runs',json=payload)
        assert first.status_code==202
        same=client.post('/api/runs',json=payload).json()
        assert same['duplicate'] and same['run']['id']==first.json()['run']['id']
        state=client.get('/api/state').json()
        assert state['mode']=='Scripted demo mode' and state['metrics']['processed']==8
        detail=client.get('/api/tickets/5').json()
        assert detail['reviews'][0]['status']=='pending'
        assert client.post('/api/reviews/'+str(detail['reviews'][0]['id']),json={'decision':'approved'}).json()['simulated_only']
        assert client.post('/api/reset',headers={'Origin':'https://evil.example'}).status_code==403
        assert client.post('/api/reset').status_code==200
        assert client.get('/api/state').json()['metrics']['processed']==0


def test_live_adapter_mocked_tool_calling(store,monkeypatch):
    from autonomy import GoalRuntime
    monkeypatch.setenv('OPENAI_API_KEY','test-key-not-real')
    turns=iter([
        [('list_open_tickets',{})],
        [('get_customer',{'ticket_id':1,'customer_id':1})],
        [('search_policies',{'ticket_id':1,'query':'billing invoice'})],
        [('save_reply_draft',{'ticket_id':1,'body':'Your invoice includes a $49 plan and $12.25 prorated seat.','policy_ids':['BILL-01']})],
        [('update_ticket',{'ticket_id':1,'status':'drafted'})],
        [('get_ticket_state',{'ticket_id':1})],
        [('get_reply_drafts',{'ticket_id':1})],
        [('get_review_records',{'ticket_id':1})],
        [('verify_ticket_outcome',{'ticket_id':1})],
        [('finish_task',{})],
    ])
    def handler(request):
        payload=json.loads(request.content)
        assert payload['tools'] and payload['parallel_tool_calls'] is False
        assert 'operator_goal' in payload['messages'][1]['content']
        calls=next(turns)
        return httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':'Do not persist this model reasoning.','tool_calls':[{'id':f'call-{n}','type':'function','function':{'name':name,'arguments':json.dumps(args)}} for n,(name,args) in enumerate(calls)]}}]})
    engine=Engine(store,scripted=False,transport=httpx.MockTransport(handler))
    run,_=store.start_run(TASK,'mock-goal-request',engine.mode)
    result=engine.run(run['id'],TASK,operation='process',ticket_ids=[1])
    assert result['status']=='completed'
    assert store.ticket(1)['status']=='drafted'
    assert store.rows('SELECT outcome FROM verifications')[-1]['outcome']=='completed'
    assert 'model reasoning' not in json.dumps(store.snapshot())


def test_live_error_does_not_silently_fallback(store,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','secret-do-not-log')
    engine=Engine(store,scripted=False,transport=httpx.MockTransport(lambda req:httpx.Response(401,json={'error':'secret-do-not-log'})))
    run,_=store.start_run(TASK,'live-failure-request',engine.mode)
    engine.run(run['id'],TASK)
    assert len(store.rows("SELECT * FROM outcomes WHERE status='failed'"))==8
    assert not store.rows('SELECT * FROM drafts')
    assert 'secret-do-not-log' not in json.dumps(store.snapshot())


def test_policy_and_context_required_before_draft(store):
    tools=runner(store,1)
    with pytest.raises(BoundaryError): tools.call('save_reply_draft',{'ticket_id':1,'body':'Here is your invoice explanation.','policy_ids':['BILL-01']})
    tools.call('get_customer',{'customer_id':1})
    tools.call('search_policies',{'query':'billing'})
    with pytest.raises(BoundaryError): tools.call('save_reply_draft',{'ticket_id':1,'body':'Here is your invoice explanation.','policy_ids':['MADE-UP']})


def test_one_click_seeded_demo_is_atomic_and_idempotent(store):
    engine=Engine(store,scripted=True)
    with TestClient(create_app(store,engine)) as client:
        payload={'task':TASK,'request_key':'one-click-demo-1','demo_failure':True}
        first=client.post('/api/demo',json=payload)
        assert first.status_code==202
        assert client.get('/api/state').json()['metrics']=={'processed':8,'escalated':3,'failed':0,'retries':1}
        same=client.post('/api/demo',json=payload).json()
        assert same['duplicate'] and same['run']['id']==first.json()['run']['id']
        assert len(store.rows('SELECT * FROM drafts'))==8
        assert len(store.rows('SELECT * FROM reviews'))==3
        # An active run must prevent a new seeded-demo reset from deleting its state.
        active,_=store.start_run(TASK,'active-run-key',engine.mode)
        before=store.snapshot()
        busy=client.post('/api/demo',json={**payload,'request_key':'different-demo-key'})
        assert busy.status_code==409
        assert store.snapshot()==before
        store.recover()
