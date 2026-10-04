import json
import httpx
import pytest
from core import Store, Engine, BoundaryError, BudgetError
from autonomy import GoalRuntime, READS

@pytest.fixture
def store(tmp_path):return Store(tmp_path/'autonomy.sqlite3')


def goal(store,operation='process',ids=None):
    engine=Engine(store,scripted=True)
    run,_=store.start_run('A scoped operator goal','autonomy-test-request',engine.mode)
    return GoalRuntime(engine,run['id'],'A scoped operator goal',False,operation,ids or [1])


def draft(g,tid=1,cid=1):
    g.call('get_customer',{'ticket_id':tid,'customer_id':cid})
    policies=g.call('search_policies',{'ticket_id':tid,'query':'billing invoice refund plan'})
    g.call('save_reply_draft',{'ticket_id':tid,'body':'Your request is recorded. Please use Settings > Billing for your plan.','policy_ids':[p['id'] for p in policies]})


def read_verify(g,tid):
    for name in READS:g.call(name,{'ticket_id':tid})
    return g.call('verify_ticket_outcome',{'ticket_id':tid})


def test_completion_rejected_without_persisted_read_back(store):
    g=goal(store);g.call('list_open_tickets',{});draft(g)
    g.call('update_ticket',{'ticket_id':1,'status':'drafted'})
    assert not g.call('finish_task',{})['accepted']
    failed=g.call('verify_ticket_outcome',{'ticket_id':1})
    assert not failed['verified'] and failed['missing_evidence']
    assert read_verify(g,1)['verified']
    assert g.call('finish_task',{})['accepted']


def test_read_back_verification_becomes_stale_after_mutation(store):
    g=goal(store,operation='draft_only');g.call('list_open_tickets',{});draft(g)
    assert read_verify(g,1)['verified']
    g.call('save_reply_draft',{'ticket_id':1,'body':'Duplicate draft call is still observable and requires rechecking.','policy_ids':['BILL-01']})
    assert not g.call('finish_task',{})['accepted']
    assert len(store.rows('SELECT * FROM drafts'))==1


def test_draft_only_preserves_status_and_audit_reports_missing_evidence(store):
    g=goal(store,operation='draft_only',ids=[7]);g.call('list_open_tickets',{});draft(g,7,1)
    with pytest.raises(BoundaryError):g.call('update_ticket',{'ticket_id':7,'status':'drafted'})
    result=read_verify(g,7)
    assert result['verified'] and result['outcome']=='draft_verified'
    assert store.ticket(7)['status']=='open'
    g.persist_result()
    # A separate goal uses the SAME runtime/registry with read-only permissions.
    store.recover()
    run,_=store.start_run('Check whether ticket 7 was resolved correctly','audit-request',g.engine.mode)
    audit=GoalRuntime(g.engine,run['id'],'Check whether ticket 7 was resolved correctly',False,'audit',[7])
    audit.call('list_open_tickets',{})
    with pytest.raises(BoundaryError):audit.call('save_reply_draft',{'ticket_id':7,'body':'Unwanted write attempt','policy_ids':['BILL-01']})
    result=read_verify(audit,7)
    assert result['verified'] and result['outcome']=='audit_verified'
    assert not result['resolution_verified'] and result['missing_evidence']
    assert store.ticket(7)['status']=='open'


def test_pending_refund_never_counted_as_completed_work(store):
    g=goal(store,ids=[2]);g.call('list_open_tickets',{});draft(g,2,2)
    g.call('update_ticket',{'ticket_id':2,'status':'drafted'})
    result=read_verify(g,2)
    assert result['verified'] and result['outcome']=='awaiting_human'
    finished=g.call('finish_task',{})
    assert finished['status']=='awaiting_human' and finished['completed_work']==[]
    assert finished['awaiting_human']==[2]
    assert g.persist_result()['status']=='awaiting_human'
    assert not store.rows('SELECT * FROM crm_actions')


def test_rejected_permission_calls_consume_bounded_budget(store):
    g=goal(store,operation='audit',ids=[2])
    for _ in range(12):
        with pytest.raises(BoundaryError):g.call('update_ticket',{'ticket_id':2,'status':'drafted'})
    with pytest.raises(BudgetError):g.call('get_ticket_state',{'ticket_id':2})
    assert len(store.rows('SELECT * FROM events WHERE ticket_id=2'))==12


def test_mock_model_observes_missing_evidence_and_adapts(store,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','mock-not-a-live-key')
    sequence=[('list_open_tickets',{}),('get_customer',{'ticket_id':1,'customer_id':1}),
              ('search_policies',{'ticket_id':1,'query':'billing invoice'}),
              ('save_reply_draft',{'ticket_id':1,'body':'Your invoice is $49 plus $12.25 prorated seat.','policy_ids':['BILL-01']}),
              ('update_ticket',{'ticket_id':1,'status':'drafted'}),('finish_task',{}),
              ('get_ticket_state',{'ticket_id':1}),('get_reply_drafts',{'ticket_id':1}),
              ('verify_ticket_outcome',{'ticket_id':1}),('get_review_records',{'ticket_id':1}),
              ('verify_ticket_outcome',{'ticket_id':1}),('finish_task',{})]
    step=0
    def handler(req):
        nonlocal step
        payload=json.loads(req.content)
        if step==6:
            observed=json.loads(payload['messages'][-1]['content'])
            assert observed['accepted'] is False and observed['missing_evidence']
        if step==9:
            observed=json.loads(payload['messages'][-1]['content'])
            assert observed['verified'] is False and observed['missing_evidence']
        name,args=sequence[step];step+=1
        return httpx.Response(200,json={'choices':[{'message':{'tool_calls':[{'id':f'call-{step}','type':'function','function':{'name':name,'arguments':json.dumps(args)}}]}}]})
    engine=Engine(store,scripted=False,transport=httpx.MockTransport(handler))
    run,_=store.start_run('Handle open billing questions','adaptive-request',engine.mode)
    result=engine.run(run['id'],'Handle open billing questions',ticket_ids=[1])
    assert result['status']=='completed' and step==12
    assert len(store.rows('SELECT * FROM drafts'))==1
    assert [v['outcome'] for v in store.rows('SELECT * FROM verifications')]==['unverified','completed']


def test_rerun_recovers_cached_update_after_verification_failure(store):
    g=goal(store);g.call('list_open_tickets',{});draft(g)
    g.call('update_ticket',{'ticket_id':1,'status':'drafted'})
    assert g.persist_result('Missing verification.')['status']=='completed_with_errors'
    assert store.ticket(1)['status']=='failed'
    run,_=store.start_run('Retry the incomplete goal','recovery-request',g.engine.mode)
    result=g.engine.run(run['id'],'Retry the incomplete goal',ticket_ids=[1])
    assert result['status']=='completed' and store.ticket(1)['status']=='drafted'
    assert len(store.rows('SELECT * FROM drafts WHERE ticket_id=1'))==1
