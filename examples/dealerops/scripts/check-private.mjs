// Private verification helper: credentials are read only from hidden stdin.
import {spawnSync} from 'node:child_process';
if(process.stdin.isTTY)process.stdin.setRawMode(true);
process.stdout.write('Ready for private verification JSON on hidden stdin.\n');
let input='';process.stdin.setEncoding('utf8');process.stdin.on('data',d=>{input+=d;if(!input.includes('\n'))return;process.stdin.pause();const c=JSON.parse(input.trim());const r=spawnSync(process.execPath,['--use-env-proxy','scripts/verify-api.mjs',c.url],{env:{...process.env,SITE_BYPASS_TOKEN:c.token},encoding:'utf8',timeout:120000});process.stdout.write(r.stdout||'');process.stderr.write(r.stderr||'');process.exit(r.status??1);});
