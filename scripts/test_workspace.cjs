const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=path.resolve(__dirname,'..','site');
const src=fs.readFileSync(path.join(root,'app.js'),'utf8').split("window.addEventListener('hashchange'")[0];
const location={href:'https://example.com/',hash:''};
const api=vm.runInNewContext(src+'\n({currentId,currentView,scopeHref,collectVideoRows,filterVideoRows,coverageFor,videoCsv,issuesFor,collectorStatus,clockStatus,newestSnapshot,newestHealth})',{Intl,URL,Date,location});
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
assert.equal(new Set(config.map(c=>c.assetLibraryUrl)).size,config.length,'Libraries must remain separate');
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
