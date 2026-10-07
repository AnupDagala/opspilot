import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
for(const file of ['intake.workflow.json','error.workflow.json','verification.workflow.json']){
 const d=JSON.parse(await readFile('n8n/'+file,'utf8'));assert.ok(d.nodes.length>1);const names=new Set(d.nodes.map(n=>n.name));assert.equal(names.size,d.nodes.length);assert.equal(d.active,false);
 for(const [source,outputs] of Object.entries(d.connections)){assert.ok(names.has(source));for(const list of outputs.main)for(const edge of list)assert.ok(names.has(edge.node));}
 for(const n of d.nodes){assert.ok(n.typeVersion);if(n.type==='n8n-nodes-base.code')new Function(n.parameters.jsCode);}
 assert.ok(!JSON.stringify(d).includes('sk-'));console.log(file+': graph and Code syntax valid; runtime execution is a separate check');
}
