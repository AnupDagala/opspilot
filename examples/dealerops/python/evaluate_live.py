"""Compare two prompts against the same held-out cases using a real provider."""
import argparse,json,os,statistics
from pathlib import Path
from langchain_service import extract_live
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--limit',type=int,default=60);p.add_argument('--output',default='artifacts/live-prompt-evaluation.json');a=p.parse_args()
 if not os.getenv('OPENAI_API_KEY') or not os.getenv('OPENAI_MODEL'):raise SystemExit('Real provider credentials and model are required. No mocked fallback is used.')
 root=Path(__file__).resolve().parent.parent;cases=json.loads((root/'evidence/evaluation-cases.json').read_text())[:a.limit];results=[]
 for version in ['v1','v2']:
  for i,c in enumerate(cases):
   try:
    d=extract_live(c['message'],version);x=d['extraction'];passed=(x.get('reason')=='multiple_items') if c.get('checkStatusOnly',False) else (x['sku']==c['sku'] and x['quantity']==c['quantity'])
    results.append({'version':version,'case':i,'passed_field_extraction':passed,**d})
   except Exception:results.append({'version':version,'case':i,'passed_field_extraction':False,'error':'provider_or_validation_failure'})
 summary={v:{'cases':len(cases),'field_extraction_passed':sum(r.get('passed_field_extraction',False) for r in results if r['version']==v),'latency_ms_median':statistics.median([r['latency_ms'] for r in results if r['version']==v and 'latency_ms' in r]) if any(r['version']==v and 'latency_ms' in r for r in results) else None} for v in ['v1','v2']}
 path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps({'mode':'real_provider','scope':'Field extraction only; business safeguards tested separately','model':os.environ['OPENAI_MODEL'],'summary':summary,'results':results},indent=2));print(json.dumps(summary,indent=2))
