const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../site/app.js'),'utf8').split("window.addEventListener('hashchange'")[0];
let mobile=true;
const nodes=new Map();
const node=id=>{if(!nodes.has(id))nodes.set(id,{hidden:true,disabled:false,innerHTML:'Loading your workspace…',textContent:'',inert:false,attrs:{},setAttribute(k,v){this.attrs[k]=v},removeAttribute(k){delete this.attrs[k]}});return nodes.get(id);};
const document={body:{classList:{remove(){}}},getElementById:node};
const api=vm.runInNewContext(source+'\n({closeNavigation,load})',{
 Intl,URL,Date,document,location:{href:'https://example.com/',hash:''},
 matchMedia:()=>({matches:mobile}),AbortSignal:{timeout:()=>undefined},fetch:async()=>{throw Error('Offline')}
});
node('sidebar').inert=false;node('main').inert=true;node('sidebar-backdrop').hidden=false;
api.closeNavigation();
assert.equal(node('sidebar').inert,true,'Closed phone navigation must not be focusable');
assert.equal(node('main').inert,false,'Closing navigation must restore main content');
assert.equal(node('sidebar-backdrop').hidden,true);
assert.equal(node('menu-toggle').attrs['aria-expanded'],'false');
mobile=false;api.closeNavigation();assert.equal(node('sidebar').inert,false,'Desktop navigation must remain usable');
module.exports=api.load().then(()=>{
 assert.equal(node('workspace-error').hidden,false,'Cold-start failure must be visible without opening Data status');
 assert.ok(node('stats').innerHTML.includes('Could not load your workspace'));
 assert.ok(!node('stats').innerHTML.includes('Loading your workspace'));
 assert.equal(node('reload').disabled,false,'Refresh must remain available after failure');
 console.log('PASS: mobile/desktop navigation focusability and visible recoverable initial load failure.');
});
