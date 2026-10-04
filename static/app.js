let selected = 1, state = null, detailSignature = '', requestKey = null, demoRequestKey = null, submitting = false;
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const meanings = {open:'Waiting for processing.', drafted:'Reply saved locally. Nothing was sent.', needs_review:'Human decision needed. No refund or account change was performed.', failed:'This ticket failed in isolation. Other tickets continue; retry is safe.', approved:'Human approved the local review. Refunds are simulated; nothing was sent.', rejected:'Human rejected the local review. No payment or message was sent.'};
const badge = status => `<span class="badge ${esc(status)}">${esc(status.replaceAll('_',' '))}</span>`;
function notice(text) { $('notice').textContent = text; $('notice').hidden = !text; }
async function api(path, options={}) {
  const res = await fetch(path,{...options,headers:{'Content-Type':'application/json',...options.headers}});
  const data = await res.json();
  if (!res.ok) throw Error(typeof data.detail==='string' ? data.detail : 'Request failed. Check your input.');
  return data;
}
const post = (path,data) => api(path,{method:'POST',body:JSON.stringify(data)});
async function selectTicket(id) { selected=id; detailSignature=''; await refresh(); }
async function loadDetail() {
  const d = await api('/api/tickets/'+selected), t=d.ticket, c=d.customer;
  const signature=JSON.stringify(d); if(signature===detailSignature) return; detailSignature=signature;
  const draft=d.drafts[0], ids=draft ? JSON.parse(draft.policy_ids) : [];
  $('detail').innerHTML=`<div class="detail-top"><div><span class="eyebrow">TICKET #${t.id} · ${esc(t.kind)}</span><h3>${esc(t.title)}</h3></div>${badge(t.status)}</div><p class="outcome-meaning">${esc(meanings[t.status] || '')}</p><p class="message">${esc(t.body)}</p>
  <div class="section-label">Customer context</div><div class="context"><div><span>CUSTOMER</span><strong>${esc(c.name)}</strong></div><div><span>COMPANY / PLAN</span><strong>${esc(c.company)} / ${esc(c.plan)}</strong></div><div class="span-all"><span>LOCAL INVOICE RECORD</span><strong>${esc(c.invoice)}</strong></div></div>
  ${d.preferences.map(p=>`<div class="memory">Memory · ${esc(p.key)}: ${esc(p.value)} · learned from ticket #${p.source_ticket}</div>`).join('')}
  <div class="section-label">Decision summary · observable actions</div><p class="summary">${esc(t.summary || 'Waiting for the worker. No actions taken.')}</p>
  <div class="section-label">Reply draft · not sent</div>${draft ? `<p class="message draft">${esc(draft.body)}</p>` : '<p class="empty">No reply draft yet.</p>'}
  <div class="section-label">Policy references</div>${d.policies.filter(p=>ids.includes(p.id)).map(p=>`<details class="policy"><summary>${esc(p.id)} · ${esc(p.title)}</summary><p>${esc(p.body)}</p></details>`).join('') || '<p class="empty">Policy references appear after drafting.</p>'}
  <div class="section-label">Independent persisted-state verification</div>${(d.verification || []).map(v=>`<details class="policy"><summary>${esc(v.outcome.replaceAll('_',' '))} · ${esc(v.operation)} · SQLite read-back</summary><pre class="verification-data">${esc(JSON.stringify(JSON.parse(v.evidence),null,2))}</pre><p>${esc(JSON.parse(v.missing).join(' ') || 'Required evidence observed.')}</p></details>`).join('') || '<p class="empty">No verification yet. A worker cannot claim completion without persisted read-back evidence.</p>'}
  ${d.crm_actions.map(a=>`<p class="memory">${esc(a.action)}</p>`).join('')}`;
}
async function refresh() {
  try {
    state = await api('/api/state');
    $('mode').textContent=state.mode;
    $('modeDescription').textContent=state.scripted ? 'Deterministic scenario logic; no live LLM reasoning. The same validated tools and SQLite persistence are used.' : 'Model-selected actions from actual tool results. Completion requires independent persisted-state verification.';
    const latest=state.runs[0], active=latest?.status==='running';
    $('run').disabled=active || submitting; $('reset').disabled=active || submitting; $('demo').disabled=active || submitting;
    $('runStatus').textContent=latest ? `${latest.status.replaceAll('_',' ')} · run ${latest.id.slice(0,8)} · ${latest.mode}` : 'Ready to process 8 fictional tickets';
    for(const key of ['processed','escalated','failed','retries']) $(key).textContent=state.metrics[key];
    $('ticketCount').textContent=state.tickets.length;
    $('tickets').innerHTML=state.tickets.map(t=>`<button class="ticket ${t.id===selected?'selected':''}" data-ticket="${t.id}"><div class="ticket-top"><span class="id">#${String(t.id).padStart(3,'0')}</span>${badge(t.status)}</div><span class="ticket-title">${esc(t.title)}</span><small>${esc(t.name)} · ${esc(t.company)}</small></button>`).join('');
    const pending=state.reviews.filter(r=>r.status==='pending'); $('reviewCount').textContent=pending.length;
    $('reviews').innerHTML=state.reviews.length ? state.reviews.map(r=>`<div class="review"><div class="ticket-top"><span class="run-line">TICKET #${r.ticket_id} · ${esc(r.name)}</span>${badge(r.status)}</div><p class="review-title">${esc(r.title)}</p><p class="review-note">${r.reason==='refund'?'Refund approval required. Approval records a simulated local CRM action only. No payment is issued.':r.reason==='clarification'?'Customer intent is unclear. Review the draft clarification before proceeding.':'Worker uncertainty requires human review.'}</p>${r.status==='pending'?`<div class="review-actions"><button class="approve" data-review="${r.id}" data-decision="approved" ${active?'disabled':''}>${r.reason==='refund'?'Approve simulated refund':'Approve review'}</button><button class="reject" data-review="${r.id}" data-decision="rejected" ${active?'disabled':''}>Reject</button></div>`:''}</div>`).join('') : '<p class="empty">No reviews yet. Refunds and unclear requests will appear here.</p>';
    const filter=$('eventFilter').value;
    const events=state.events.filter(e=>filter==='selected'?e.ticket_id===selected:filter==='recovery'?e.ticket_id===4 && e.tool==='get_customer':true);
    const eventSignature=JSON.stringify({events,filter});
    if($('events').dataset.signature!==eventSignature) {
      $('events').dataset.signature=eventSignature;
      $('events').innerHTML=events.length ? events.map(e=>`<div class="event ${e.error?'error':''}"><div class="event-line"><span class="event-name">${esc(e.tool)}</span><span>${e.error?'RETRY / ERROR':'OK'} · ${e.duration_ms}ms</span></div><div class="event-meta">${e.ticket_id?'Ticket #'+e.ticket_id:'Run discovery'} · attempt ${e.attempt} · run ${e.run_id.slice(0,8)} · ${esc(e.created)} UTC</div><details><summary>${e.error?esc(e.error):'Validated input & result'}</summary><pre>Input: ${esc(e.inputs)}\nResult: ${esc(e.result)}${e.error?'\nError: '+esc(e.error):''}</pre></details></div>`).join('') : '<p class="empty">No matching activity yet. Run the seeded demo or choose All tool activity.</p>';
    }
    await loadDetail();
  } catch(err) { notice('Cannot reach the local worker. '+err.message+' Start the server using the README commands, then reload.'); }
}
$('eventFilter').addEventListener('change',refresh);
$('demo').addEventListener('click',async()=>{
  if(submitting || !state)return; submitting=true; $('demo').disabled=true; $('run').disabled=true; $('reset').disabled=true; notice('Preparing the eight fictional scenarios…');
  demoRequestKey=demoRequestKey || crypto.randomUUID();
  try {
    const result=await post('/api/demo',{task:'Process open tickets, look up each customer, draft appropriate replies, update the CRM, and escalate refunds or unclear cases.',request_key:demoRequestKey,demo_failure:true});
    demoRequestKey=null; selected=1; detailSignature=''; $('eventFilter').value='all';
    notice(result.duplicate?'Existing seeded run recovered; no duplicate work.':state.scripted?'Scripted seeded demo started: eight fictional scenarios using real local tools and persistence.':'Seeded live LLM run started using your configured provider.');
  }catch(err){notice(err.message+' Retry uses the same demo request key.');}
  finally{submitting=false;await refresh();}
});
$('tickets').addEventListener('click',event=> { const b=event.target.closest('[data-ticket]'); if(b) selectTicket(Number(b.dataset.ticket)); });
$('reviews').addEventListener('click',async event=>{
  const b=event.target.closest('[data-review]'); if(!b)return; b.disabled=true;
  try { await post('/api/reviews/'+b.dataset.review,{decision:b.dataset.decision}); notice('Human decision recorded locally. No message or payment sent.'); detailSignature=''; await refresh(); } catch(err) {notice(err.message);b.disabled=false;}
});
$('run').addEventListener('click',async()=>{
  if(submitting || !state)return; submitting=true; $('run').disabled=true; notice('');
  requestKey=requestKey || crypto.randomUUID();
  try { const result=await post('/api/runs',{task:$('task').value,request_key:requestKey,demo_failure:$('failure').checked,operation:$('operation').value,ticket_ids:$('scope').value.trim() ? $('scope').value.split(',').map(x=>Number(x.trim())) : []}); requestKey=null; notice(result.duplicate?'Existing run recovered; no duplicate work.':state.scripted?'Scripted demo started. Your task is recorded; this mode processes the predefined support workflow.':'Live LLM worker started.'); }
  catch(err) {notice(err.message+' Retry uses the same request key to prevent duplicate work.');}
  finally {submitting=false;await refresh();}
});
$('reset').addEventListener('click',async()=>{
  if(!confirm('Reset only OpsPilot fictional local data, drafts, reviews, memory and run history?'))return;
  try {await post('/api/reset',{});selected=1;detailSignature='';requestKey=null;notice('Local demo data reset.');await refresh();}catch(err){notice(err.message);}
});
document.querySelector('.goal-examples').addEventListener('click',event=>{
  const goal=event.target.dataset.goal;if(!goal)return;
  const goals={billing:['Handle open billing questions, draft replies using our policies, and escalate refund requests.','process','1,2,5'],draft:["Review ticket 7, retrieve the customer's preferences, and draft a reply without changing its status.",'draft_only','7'],audit:['Check whether ticket 2 was resolved correctly and report any missing evidence.','audit','2']};
  $('task').value=goals[goal][0];$('operation').value=goals[goal][1];$('scope').value=goals[goal][2];
  notice('Goal loaded. The execution contract enforces scope and permissions; the live model chooses the tool sequence.');
});
refresh(); setInterval(refresh,1000);
