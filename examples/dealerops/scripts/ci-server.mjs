// CI-only HTTP bridge for n8n. Memory storage is intentionally non-production.
import http from 'node:http';
import {handle} from '../worker/core.mjs';
class MemoryBucket{constructor(){this.rows=new Map();this.rev=0;}async get(k){const o=this.rows.get(k);return o?{etag:o.etag,json:async()=>JSON.parse(o.body)}:null;}async put(k,body,opts={}){if(opts.onlyIf&&this.rows.get(k)?.etag!==opts.onlyIf.etagMatches)return null;const o={body,etag:String(++this.rev)};this.rows.set(k,o);return o;}}
const bucket=new MemoryBucket();
http.createServer(async(req,res)=>{try{let body='';for await(const chunk of req){body+=chunk;if(body.length>8192){res.writeHead(413);res.end();return;}}const r=await handle(new Request('http://127.0.0.1:8788'+req.url,{method:req.method,headers:req.headers,...(body?{body}:{})}),{BUCKET:bucket},'CI-only handler bridge');res.writeHead(r.status,Object.fromEntries(r.headers));res.end(await r.text());}catch{res.writeHead(500);res.end();}}).listen(8788,'127.0.0.1',()=>console.log('CI-only synthetic Worker bridge ready on 8788'));
