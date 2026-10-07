"""Read-only real Google Sheets adapter. Useful for verifying a sandbox integration."""
import json,os,urllib.request,urllib.parse
def read_inventory():
    token=os.getenv('GOOGLE_ACCESS_TOKEN');sheet=os.getenv('GOOGLE_SHEET_ID')
    if not token or not sheet:raise RuntimeError('GOOGLE_ACCESS_TOKEN and GOOGLE_SHEET_ID are required')
    url='https://sheets.googleapis.com/v4/spreadsheets/'+urllib.parse.quote(sheet,safe='')+'/values/'+urllib.parse.quote('Inventory!A1:D100',safe='')
    req=urllib.request.Request(url,headers={'Authorization':'Bearer '+token})
    with urllib.request.urlopen(req,timeout=20) as r:data=json.load(r)
    return {'mode':'live_google_sheets_read_only','range':data.get('range'),'rows':data.get('values',[])}
if __name__=='__main__':print(json.dumps(read_inventory(),indent=2))
