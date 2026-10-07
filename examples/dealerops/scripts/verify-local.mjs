// Execute real Worker Request handlers against a file-backed R2 contract emulator.
// This does not claim a browser, network request, or real Cloudflare R2 execution.
import {readFileSync,writeFileSync,renameSync,existsSync,mkdirSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {handle} from '../worker/core.mjs';
const folder='artifacts/local-storage';mkdirSync(folder,{recursive:true});
class FileBucket {
 path(k){return folder+'/'+k.replaceAll('/','_')+'.json';}
 async get(k){const p=this.path(k);if(!existsSync(p))return null;const value=readFileSync(p,'utf8');return {etag:createHash('sha256').update(value).digest('hex'),json:async()=>JSON.parse(value)};}
 async put(k,value,opts={}){const p=this.path(k);if(opts.onlyIf){if(!existsSync(p))return null;const current=createHash('sha256').update(readFileSync(p)).digest('hex');if(current!==opts.onlyIf.etagMatches)return null;}const temp=p+'.tmp';writeFileSync(temp,value);renameSync(temp,p);return {etag:createHash('sha256').update(value).digest('hex')};}
}
const bucket=new FileBucket();globalThis.fetch=async(url,options)=>handle(new Request(url,options),{BUCKET:bucket},'<h1>DealerOps local execution harness</h1>');
process.env.DEALEROPS_INPROCESS='1';process.argv[2]='https://local-worker.invalid';
await import('./verify-api.mjs');
