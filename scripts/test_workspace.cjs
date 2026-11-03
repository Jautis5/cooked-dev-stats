const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=path.resolve(__dirname,'..','site');
const src=fs.readFileSync(path.join(root,'app.js'),'utf8').split("window.addEventListener('hashchange'")[0];
const location={href:'https://example.com/',hash:''};
const api=vm.runInNewContext(src+'\n({currentId,currentView,scopeHref,collectVideoRows,filterVideoRows,coverageFor,videoCsv,issuesFor,collectorStatus,clockStatus,newestSnapshot,newestHealth,scheduleState,missingPublication,inventoryAudit,accountState,inventoryText})',{Intl,URL,Date,location});
location.hash='#channel/indian-builds/videos';
assert.equal(api.currentId(),'indian-builds');assert.equal(api.currentView(),'videos');
location.hash='#accounts';assert.equal(api.currentId(),'');assert.equal(api.currentView(),'accounts');
location.hash='#channel/cooked-dev';assert.equal(api.currentId(),'cooked-dev');assert.equal(api.currentView(),'overview');
assert.equal(api.scopeHref('indian-builds','accounts'),'#channel/indian-builds/accounts');
assert.equal(api.scopeHref(null,'videos'),'#videos');
const channels=[{id:'cooked-dev',name:'Cooked Dev'},{id:'indian-builds',name:'Indian Builds'}];
const accounts=[{id:'instagram',name:'Instagram',status:'ok'},{id:'tiktok',name:'TikTok',status:'ok'}];
const post=(value,url)=>({url,metrics:{views:{value,at:'2026-10-20T10:00:00Z',source:url}}});
const records=new Map([
 ['cooked-dev',{data:{accounts,videos:[{id:'same-id',caption:'Same caption',posts:{instagram:post(0,'https://example.com/cooked/ig')}}]}}],
 ['indian-builds',{data:{accounts,videos:[{id:'same-id',caption:'Same caption',posts:{instagram:post(20,'https://example.com/indian/ig'),tiktok:{url:'https://example.com/indian/tt',metrics:{}}}},{id:'formula',caption:'=HYPERLINK("x")',posts:{}}]}}]
]);
const rows=api.collectVideoRows(channels,records);
assert.equal(rows.length,3,'Identical post ids or captions across brands must remain separate');
assert.equal(api.filterVideoRows(rows,{channel:'cooked-dev'}).length,1);
assert.equal(api.filterVideoRows(rows,{channel:'indian-builds'})[0].channel.id,'indian-builds');
assert.equal(api.filterVideoRows(rows,{term:'indian'})[0].channel.id,'indian-builds');
assert.equal(api.filterVideoRows(rows,{coverage:'complete'}).length,1);
assert.equal(api.filterVideoRows(rows,{platform:'tiktok',coverage:'gaps'}).length,2);
assert.equal(api.filterVideoRows(rows,{platform:'tiktok',coverage:'complete'}).length,1);
assert.equal(api.filterVideoRows(rows,{platform:'facebook'}).length,0);
assert.equal(api.filterVideoRows(rows,{sort:'views'})[0].channel.id,'indian-builds');
assert.equal(api.coverageFor(rows[0]).confirmed,1);assert.equal(api.coverageFor(rows[0]).gaps,1);
const csv=api.videoCsv(rows);
assert.ok(csv.includes('Cooked Dev'));assert.ok(csv.includes('Indian Builds'));
assert.ok(csv.includes('"Not confirmed",""'), 'Unknown publications must not become published or real zero metrics');
assert.ok(csv.includes('"0","2026-10-20T10:00:00Z","false"'), 'Measured zero must remain a zero with its observation timestamp');
assert.ok(csv.includes('"\'=HYPERLINK(""x"")"'), 'Source captions must not execute as spreadsheet formulas');
const tt=api.videoCsv(rows,'tiktok');assert.ok(!tt.includes('https://example.com/cooked/ig'));assert.ok(tt.includes('https://example.com/indian/tt'));
const missing=api.issuesFor(channels,new Map());assert.equal(missing.length,2);
assert.ok(api.issuesFor(channels,records).some(i=>i.channel.id==='indian-builds'&&i.title.includes('no view count')));
const config=JSON.parse(fs.readFileSync(path.join(root,'data/channels.json'))).channels;
const libraries=config.map(c=>c.assetLibraryUrl).filter(Boolean);
assert.equal(new Set(libraries).size,libraries.length,'Registered libraries must remain separate; unconfigured libraries are allowed');
console.log('PASS: independent channel routes, duplicate ids, combined search, platform gaps, measured zero vs unknown, source-preserving CSV and formula-safe export.');

const healthNow=Date.now();
assert.equal(api.collectorStatus(null,healthNow).warning,true);
assert.equal(api.collectorStatus({provider:'local_verification'},healthNow).warning,true);
const health={provider:'GitHub Actions',completedAt:new Date(healthNow).toISOString(),status:'completed',channels:{one:{metricsUpdated:5}}};
assert.equal(api.collectorStatus(health,healthNow).warning,false);
assert.equal(api.collectorStatus({...health,trigger:'workflow_dispatch'},healthNow).label,'On-demand collection completed');
assert.equal(api.collectorStatus({...health,initiator:'continuous_clock'},healthNow).label,'Automatic collection completed');
assert.equal(api.clockStatus([],healthNow).warning,true);
const clockRun={id:1,status:'waiting',created_at:new Date(healthNow-60000).toISOString(),html_url:'https://github.com/example/repo/actions/runs/1'};
assert.equal(api.clockStatus([clockRun],healthNow).warning,false);
assert.equal(api.clockStatus([clockRun],healthNow).targetAt,healthNow+14*60000);
assert.equal(api.clockStatus([clockRun],healthNow+3600000).warning,true);
assert.equal(api.collectorStatus({...health,trigger:'schedule'},healthNow).label,'Scheduled collection completed');
assert.equal(api.collectorStatus({...health,trigger:'workflow_dispatch'},healthNow+3*3600000).label,'Automatic updates delayed');
assert.equal(api.collectorStatus(health,healthNow+3*3600000).warning,true);
health.channels.one.metricsUpdated=0;assert.equal(api.collectorStatus(health,healthNow).warning,true);

const cached={data:{lastAttemptAt:'2026-10-20T09:00:00Z'},fallback:false};
const bundled={data:{lastAttemptAt:'2026-10-20T11:00:00Z'},fallback:true};
assert.equal(api.newestSnapshot([cached,bundled]).data.lastAttemptAt,bundled.data.lastAttemptAt);
assert.equal(api.newestSnapshot([bundled,{...bundled,fallback:false}]).fallback,false);
assert.equal(api.newestSnapshot([]),null);

assert.equal(api.newestHealth([{...health,version:1,completedAt:'2026-10-20T12:00:00Z'},{...health,version:1,completedAt:'2026-10-20T13:00:00Z'}]).completedAt,'2026-10-20T13:00:00Z');
assert.equal(api.newestHealth([]),null);
const scheduleNow=Date.parse('2026-10-22T12:00:00Z');
assert.equal(api.scheduleState({status:'pending',scheduledAt:'2026-10-23T16:10:00Z'},scheduleNow).label,'Not scheduled');
assert.equal(api.scheduleState({status:'save_submitted',scheduledAt:'2026-10-23T16:10:00Z'},scheduleNow).label,'Verify saved schedule');
assert.equal(api.scheduleState({status:'scheduled',scheduledAt:'2026-10-23T16:10:00Z'},scheduleNow).label,'Scheduled');
assert.equal(api.scheduleState({status:'scheduled',scheduledAt:'2026-10-21T16:10:00Z'},scheduleNow).label,'Due · verify publication');
assert.equal(api.scheduleState({status:'scheduled'},scheduleNow).warning,true);
console.log('PASS: planned and submitted posts stay unconfirmed; elapsed schedules never become published automatically.');
const inventoryNow=Date.parse('2026-10-22T18:00:00Z');
const inventoryData={discovery:{instagram:{complete:false,checkedAt:'2026-10-22T18:00:00Z',lastCompleteAt:'2026-10-22T06:00:00Z'}}};
assert.equal(api.inventoryAudit(inventoryData,{id:'instagram'},inventoryNow).overdue,true);
inventoryData.discovery.instagram.lastCompleteAt='2026-10-22T17:00:00Z';
assert.equal(api.inventoryAudit(inventoryData,{id:'instagram'},inventoryNow).overdue,false);
assert.equal(api.inventoryAudit(inventoryData,{id:'instagram'},inventoryNow).complete,false);
const recentInventory={...inventoryData,videos:[]};
assert.equal(api.accountState(recentInventory,{id:'instagram',status:'partial'},inventoryNow).label,'Full list recently checked','A later partial cloud check must not erase a recent full browser verification');
assert.equal(api.accountState(recentInventory,{id:'instagram',status:'partial'},inventoryNow).warning,true,'Recent inventory verification must not imply all metrics refreshed');
assert.ok(api.inventoryText(recentInventory,{id:'instagram'},inventoryNow).includes('latest source check was partial'));
assert.equal(api.accountState(recentInventory,{id:'instagram'},inventoryNow+2*3600000).label,'New-video check overdue');
assert.notEqual(api.accountState({discovery:{}},{id:'instagram',status:'ok'}).label,'Checked','Known-post metrics cannot imply successful new-post discovery');
console.log('PASS: fresh likes do not conceal overdue or incomplete publication discovery.');

const emptyAccount={id:'tiktok',name:'TikTok',emptyConfirmedAt:'2026-10-22T13:40:00Z',metrics:{publishedCount:{value:0}}};
assert.ok(api.missingPublication(emptyAccount,{videos:[]}).includes('TT · empty'));
assert.ok(!api.missingPublication({...emptyAccount,metrics:{}},{videos:[]}).includes('TT · empty'));
assert.ok(!api.missingPublication(emptyAccount,{videos:[{posts:{tiktok:{id:'known'}}}]}).includes('TT · empty'));

module.exports=(async()=>{
 const registryChannels=['cooked-dev','indian-builds','dont-get-traced','dumb-luck','no-code-kevin','barely-shipped'].map(id=>({id,name:id,dataUrl:'https://feeds.example/'+id+'.json',fallbackUrl:'data/'+id+'.json',logo:'assets/logo.jpg'}));
 const nodes=new Map(),node=id=>{if(!nodes.has(id))nodes.set(id,{value:'',hidden:true,disabled:false,innerHTML:'',parentElement:{hidden:false}});return nodes.get(id);};
 const route={href:'https://example.com/',hash:'#channel/cooked-dev/videos'},icon={};
 const controls={search:'keep this query',sort:'likes','video-channel':'cooked-dev','video-coverage':'gaps'};
 for(const [id,value]of Object.entries(controls))node(id).value=value;
 let cycle=0,registryFetches=0;
 const fetched=[];
 const refreshed=vm.runInNewContext(src+`\n
  render=()=>{renderNavigation();renderVideoFilters();};
  loadClock=async()=>{};
  active='tiktok';chartRange='7d';chartScope='cooked-dev';
  ({load,state:()=>({ids:channels.map(c=>c.id),hash:location.hash,active,chartRange,chartScope,loading,at:entries.get('cooked-dev')?.data?.lastAttemptAt})})`,{
  Intl,URL,Date,location:route,AbortSignal:{timeout:()=>undefined},
  document:{body:{dataset:{}},getElementById:node,querySelector:()=>icon},
  fetch:async input=>{
   const url=new URL(input,route.href);fetched.push(url.href);
   if(url.pathname==='/data/channels.json'){
    registryFetches++;
    if(cycle===2)throw Error('Temporary registry outage');
    return {ok:true,json:async()=>cycle===3?{version:2,channels:[]}:{version:1,channels:registryChannels.slice(0,cycle===0?5:6)}};
   }
   if(url.pathname.endsWith('/health.json'))return {ok:true,json:async()=>({version:1,provider:'GitHub Actions',channels:{},completedAt:new Date().toISOString()})};
   if(url.pathname==='/data/schedules.json')return {ok:true,json:async()=>({version:1,items:[]})};
   return {ok:true,json:async()=>({version:1,lastAttemptAt:'2026-11-03T14:0'+cycle+':00Z',accounts:[{id:'tiktok',name:'TikTok'}],videos:[]})};
  }
 });
 await refreshed.load();
 assert.equal(refreshed.state().ids.length,5);
 assert.ok(!node('workspace-switcher').innerHTML.includes('barely-shipped'));
 const stateBefore=JSON.parse(JSON.stringify(refreshed.state()));
 cycle=1;await refreshed.load();
 assert.equal(registryFetches,2,'Automatic reload must fetch the current registry even when channels are already loaded');
 assert.equal(refreshed.state().ids.length,6,'A newly registered channel must appear without reloading the page');
 assert.ok(node('workspace-switcher').innerHTML.includes('data-channel="barely-shipped"'));
 assert.ok(node('video-channel').innerHTML.includes('value="barely-shipped"'));
 assert.equal(fetched.filter(url=>new URL(url).pathname.endsWith('/barely-shipped.json')).length,2,'New channel live and fallback feeds must load in the same refresh');
 for(const key of ['hash','active','chartRange','chartScope'])assert.equal(refreshed.state()[key],stateBefore[key],'Registry refresh must preserve '+key);
 for(const [id,value]of Object.entries(controls))assert.equal(node(id).value,value,'Registry refresh must preserve '+id);
 for(cycle=2;cycle<=3;cycle++){
  await refreshed.load(cycle===3);
  assert.equal(refreshed.state().ids.length,6,'An unavailable or invalid registry must preserve the last valid channel list');
  assert.equal(refreshed.state().at,'2026-11-03T14:0'+cycle+':00Z','Feed refresh must continue when the registry refresh fails');
  assert.equal(refreshed.state().loading,false);
  assert.equal(node('reload').disabled,false);
 }
 console.log('PASS: automatic and manual refresh discover new channels, preserve routes and filters, and keep feeds updating during registry failures.');
})();
module.exports.catch(error=>{console.error(error);process.exitCode=1;});
