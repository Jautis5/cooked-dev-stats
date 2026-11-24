const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../site/app.js'),'utf8').split("window.addEventListener('hashchange'")[0];
const {kitCard,validKitStats,lumoKitSection,validLumoKitStats}=vm.runInNewContext(source+'\n({kitCard,validKitStats,lumoKitSection,validLumoKitStats})',{Intl,URL,Date,location:{href:'https://example.com/',hash:''}});
const now=Date.parse('2026-11-16T15:00:00Z');
const snapshot={version:1,channelId:'cooked-dev',status:'ok',totalSubscribers:{value:1740,at:new Date(now).toISOString(),method:'kit_api_v4'}};
assert.ok(kitCard(snapshot,false,'all',now).includes('1.740'));
assert.ok(kitCard(snapshot,false,'cooked-dev',now).includes('Auto-updated'));
assert.equal(kitCard(snapshot,false,'indian-builds',now),'');
assert.equal(kitCard(snapshot,false,'barely-shipped',now),'');
assert.ok(kitCard(snapshot,true,'all',now).includes('feed unavailable'));
assert.ok(kitCard(snapshot,false,'all',now+20*60000).includes('Auto-updated'));
assert.ok(!kitCard(snapshot,false,'all',now+31*60000).includes('Auto-updated'));
assert.ok(kitCard({...snapshot,status:'authorization_required'},false,'all',now).includes('Connect Kit'));
assert.ok(kitCard({...snapshot,totalSubscribers:{...snapshot.totalSubscribers,value:0}},false,'all',now).includes('>0</div>'));
assert.equal(validKitStats({...snapshot,channelId:'other'}),false);
assert.equal(validKitStats({...snapshot,totalSubscribers:{value:null,at:snapshot.totalSubscribers.at}}),false);
assert.ok(kitCard(null,false,'all',now).includes('Waiting for Kit data'));
console.log('PASS: exact email count, real zero, channel scoping, stale/error states and subscriber link.');

const lumo={version:1,channelId:'lumo-wins',status:'partial',lastAttemptAt:new Date(now).toISOString(),
 totalSubscribers:{at:new Date(now).toISOString(),value:0},
 growth:{at:new Date(now).toISOString(),value:{7:{starting:'2026-11-10',ending:'2026-11-16',new_subscribers:4,cancellations:6,net_new_subscribers:-2}}}};
assert.equal(validLumoKitStats(snapshot),false);
assert.equal(validLumoKitStats(lumo),true);
assert.equal(kitCard(lumo,false,'lumo-wins',now),'');
assert.match(lumoKitSection(lumo,false,now),/>0<\/strong> confirmed subscribers/);
assert.match(lumoKitSection(lumo,false,now),/>-2<\/td>/);
assert.match(lumoKitSection(lumo,false,now),/Some Kit metrics could not be refreshed/);
assert.match(lumoKitSection(null,false,now),/Waiting for Kit connection/);
console.log('PASS: separate Lumo Kit feed, zero, negative net growth and partial refresh.');
