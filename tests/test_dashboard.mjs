import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const root=new URL('../',import.meta.url);
const data=fs.readFileSync(new URL('dashboard/data.js',root),'utf8');
const script=fs.readFileSync(new URL('dashboard/script.js',root),'utf8');
const html=fs.readFileSync(new URL('dashboard/index.html',root),'utf8');
const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(x=>x[1]);
const accessed=[...script.matchAll(/\$\('([^']+)'\)/g)].map(x=>x[1]);
for(const id of accessed) assert.ok(ids.includes(id),`Missing dashboard element ${id}`);

function element() {
  return {textContent:'',style:{},children:[],value:'',events:{},
    append(...x){this.children.push(...x);},
    replaceChildren(...x){this.children=x;},
    setAttribute(){},
    addEventListener(name,callback){this.events[name]=callback;},
    insertAdjacentHTML(){},
  };
}
const elements=Object.fromEntries(ids.map(id=>[id,element()]));
for(const [id,value] of Object.entries({
  'origin-filter':'traceable','assumed-leads':'1000','assumed-uplift':'1',
  'assumed-fee':'12','assumed-cost':'10000',
})) elements[id].value=value;
const context={window:{},document:{getElementById:id=>elements[id],
  createElement:element,createElementNS:element,body:element()}, console};
vm.runInNewContext(data,context);
vm.runInNewContext(script,context);
assert.equal(elements['kpi-leads'].textContent,'8,000');
assert.match(elements['kpi-gmv'].textContent,/328,334/);
assert.ok(elements['conversion-chart'].children.length>=10);
assert.ok(elements['origin-filter'].children.every(e=>!['Unknown','Missing'].includes(e.textContent)));
assert.match(elements['result-net'].textContent,/R\$ /);
const originalFee=elements['result-fees'].textContent;
elements['origin-filter'].value='paid_search';
elements['origin-filter'].events.change();
assert.match(elements['yield-value'].textContent,/R\$ 534/);
elements['assumed-uplift'].value='2';
elements['assumed-uplift'].events.input();
assert.notEqual(elements['result-fees'].textContent,originalFee);
elements['origin-filter'].value='display';
elements['origin-filter'].events.change();
assert.equal(elements['result-wins'].textContent,'Insufficient cohort');
console.log('Dashboard DOM and scenario checks passed');
