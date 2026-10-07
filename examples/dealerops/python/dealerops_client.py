"""Dependency-free API client. Never prints role credentials or provider secrets."""
import json, os, urllib.request, urllib.error

class DealerOpsClient:
    def __init__(self, base_url, session=None, operator=None, reviewer=None):
        self.base_url=base_url.rstrip('/'); self.session=session; self.operator=operator; self.reviewer=reviewer
    def request(self, path, data=None, role='operator'):
        headers={'Content-Type':'application/json'}
        if self.session:
            headers.update({'X-Demo-Session':self.session,'Authorization':'Bearer '+getattr(self,role)})
        if os.getenv('SITE_BYPASS_TOKEN'):
            headers['OAI-Sites-Authorization']='Bearer '+os.environ['SITE_BYPASS_TOKEN']
        req=urllib.request.Request(self.base_url+'/api/'+path,data=None if data is None else json.dumps(data).encode(),headers=headers,method='GET' if data is None else 'POST')
        try:
            with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
        except urllib.error.HTTPError as exc:
            try:code=json.load(exc).get('error','http_error')
            except Exception:code='http_error'
            raise RuntimeError(f'HTTP {exc.code}: {code}') from None
    def new_session(self):
        d=self.request('session',{});self.session=d['session'];self.operator=d['operator'];self.reviewer=d['reviewer'];return d['state']

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);a=p.parse_args()
    c=DealerOpsClient(a.url);c.new_session()
    d=c.request('intake',{'event_id':'python-demo','dealer':'D001','channel':'portal','message':'20 cartons AB100 tomorrow'})
    print(json.dumps({'order':d['result']['order'],'mode':'Hosted API client; no automatic approval'},indent=2))
