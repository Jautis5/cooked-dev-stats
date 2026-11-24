'use strict';
const $ = id => document.getElementById(id);
const ABBR = {instagram:'IG',tiktok:'TT',youtube:'YT',x:'X',facebook:'FB'};
const ICONS = {
 views:'<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
 likes:'<path d="M7 10h-4v11h4zm0 11h11a2 2 0 0 0 2-1.6l1.3-7A2 2 0 0 0 19.3 10H14l1-5a2.5 2.5 0 0 0-3-2L7 10Z"/>',
 followers:'<circle cx="9" cy="8" r="3.5"/><path d="M2 21v-2a7 7 0 0 1 14 0v2m1-17a3.5 3.5 0 0 1 0 7m2 3a6 6 0 0 1 3 5v2"/>',
 posts:'<rect x="3" y="3" width="18" height="18" rx="4"/><path d="m10 8 6 4-6 4Z"/>'
};
let channels=[],entries=new Map(),active='all',loading=false,chartRange='24h',chartScope='all',renderedScope='all',cloudHealth=null,cloudConfig={},clockRuns=null;
let publishingQueue=null;
let kitStats=null,kitFeedFailed=false,lumoKitStats=null,lumoKitFeedFailed=false;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const full=n=>n==null?'—':new Intl.NumberFormat('en-US').format(n);
function compact(n) {
 if(!Number.isFinite(n))return '—';
 const a=Math.abs(n),unit=a>=1e9?1e9:a>=1e6?1e6:a>=1e3?1e3:1;
 if(unit===1)return full(n);
 let value=Number((n/unit).toFixed(1)),suffix={1000:'K',1000000:'M',1000000000:'B'}[unit];
 if(Math.abs(value)>=1000&&unit<1e9){value=Number((value/1000).toFixed(1));suffix=unit===1000?'M':'B';}
 return value+suffix;
}

function headline(n){
 if(!Number.isFinite(n))return '—';
 return n>=1e6?new Intl.NumberFormat('en-US',{maximumFractionDigits:2}).format(n/1e6)+'M':n>=1e5?new Intl.NumberFormat('en-US',{maximumFractionDigits:1}).format(n/1e3)+'K':full(n);
}
const svg=(path,cls='')=>'<svg class="'+cls+'" viewBox="0 0 24 24" aria-hidden="true">'+path+'</svg>';
const NAV_ICONS={overview:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',videos:'<rect x="3" y="4" width="18" height="16" rx="3"/><path d="m10 8 6 4-6 4Z"/>',accounts:'<path d="M9 8 7 6a4 4 0 0 0-6 6l4 4a4 4 0 0 0 6 0m4 0 2 2a4 4 0 0 0 6-6l-4-4a4 4 0 0 0-6 0m-4 4 6-6"/>'};
const time=t=>{const ms=typeof t==='number'?t:Date.parse(t);return Number.isFinite(ms)?new Intl.DateTimeFormat('en-GB',{day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',timeZone:'Europe/Vilnius'}).format(new Date(ms))+' Vilnius':'Not checked';};
const safe=u=>{try{const v=new URL(u,location.href);return v.protocol==='https:'||v.origin===location.origin?esc(v.href):'#';}catch{return '#';}};
const currentId=()=>{try{return decodeURIComponent(location.hash.match(/^#channel\/([^/]+)/)?.[1]||'');}catch{return '';}};
const currentView=()=>{const part=location.hash.split('/').at(-1).replace(/^#/,'');return ['videos','accounts'].includes(part)?part:'overview';};
const selected=()=>channels.find(c=>c.id===currentId())||null;
const videoTitle=v=>String(v.caption||v.title||'Untitled video').trim();
const valid=m=>m&&Number.isFinite(m.value);
const approx=m=>m?.approximate?'<span class="approx" aria-label="Approximately">≈</span>':'';
function total(posts,key){
 const ms=posts.map(p=>p.metrics?.[key]).filter(valid);
 return {value:ms.length?ms.reduce((s,m)=>s+m.value,0):null,count:ms.length,approximate:ms.some(m=>m.approximate),oldest:ms.map(m=>m.at).filter(Boolean).sort()[0],latest:ms.map(m=>m.at).filter(Boolean).sort().at(-1)};
}
function summary(data,platform='all'){
 const accounts=data.accounts.filter(a=>platform==='all'||a.id===platform);
 const posts=data.videos.flatMap(v=>Object.entries(v.posts).filter(([p])=>platform==='all'||p===platform).map(([,p])=>p));
 const views=total(posts,'views'),likes=total(posts,'likes');
 if(!posts.length&&accounts.length&&accounts.every(a=>(a.emptyConfirmedAt&&a.metrics?.publishedCount?.value===0)||(a.trackedEmptyConfirmedAt&&a.metrics?.trackedPublishedCount?.value===0))){
  const oldest=accounts.map(a=>a.trackedEmptyConfirmedAt||a.emptyConfirmedAt).sort()[0];
  Object.assign(views,{value:0,oldest});Object.assign(likes,{value:0,oldest});
 }
 return {views,likes,followers:total(accounts,'followers'),posts:{value:posts.length,count:posts.length},postCount:posts.length,accountCount:accounts.length,videoCount:data.videos.filter(v=>Object.keys(v.posts).some(p=>platform==='all'||p===platform)).length};
}
function combine(list){
 const out={postCount:0,accountCount:0,videoCount:0};
 for(const key of ['views','likes','followers','posts']){
  const ms=list.map(s=>s[key]).filter(valid);
  out[key]={value:ms.length?ms.reduce((n,m)=>n+m.value,0):null,count:ms.reduce((n,m)=>n+(m.count||0),0),approximate:ms.some(m=>m.approximate),oldest:ms.map(m=>m.oldest).filter(Boolean).sort()[0],latest:ms.map(m=>m.latest||m.oldest).filter(Boolean).sort().at(-1)};
 }
 for(const key of ['postCount','accountCount','videoCount'])out[key]=list.reduce((n,s)=>n+s[key],0);
 return out;
}
const collectionActive=a=>a.collection?.enabled!==false;
function statusText(a){
 if(!collectionActive(a))return 'Owner deleted this account. Collection stopped; saved metrics and their original dates are historical.';
 if(a.emptyConfirmedAt&&a.metrics?.publishedCount?.value===0)return 'No public uploads observed · checked '+time(a.emptyConfirmedAt)+'.';
 if(a.trackedEmptyConfirmedAt&&a.metrics?.trackedPublishedCount?.value===0)return 'No videos in the tracked scope · checked '+time(a.trackedEmptyConfirmedAt)+'.';
 if(a.id==='youtube'&&a.status==='unavailable')return 'Content access needs verification. Last verified metrics are preserved.';
 if(a.status==='ok')return 'Available metrics for known publications refreshed. Inventory is checked separately.';
 if(a.status==='partial')return 'Some metrics updated. Each number keeps its own observation time.';
 return 'Source unavailable. Showing the last verified metrics.';
}
function missingPublication(account,data){
 const known=data.videos.some(v=>v.posts[account.id]);
 const checked=account.emptyConfirmedAt||account.trackedEmptyConfirmedAt;
 if(!known&&checked&&(account.metrics?.publishedCount?.value===0||account.metrics?.trackedPublishedCount?.value===0))
  return '<span class="post-link unconfirmed" title="'+esc(account.name+' · no public videos in scope when checked '+time(checked))+'">'+esc(ABBR[account.id]||account.name)+' · empty</span>';
 return '<span class="post-link unconfirmed" title="'+esc(account.name)+' · publication not confirmed">'+esc(ABBR[account.id]||account.name)+' —</span>';
}
function metricTitle(m){return `${m?.approximate?'Approximately ':''}${full(m?.value)} · Observed ${time(m?.at||m?.oldest)}`;}
function metricCell(m,date=true){
 if(!valid(m))return '<span class="muted">—</span>';
 return '<span class="num" tabindex="0" title="'+esc(metricTitle(m))+'">'+(m.approximate?'≈ ':'')+full(m.value)+'</span>'+(date&&(m.at||m.oldest)?'<span class="tiny">'+esc(time(m.at||m.oldest))+'</span>':'');
}
function assetLink(v){return v.assetUrl?'<a class="asset-link" href="'+safe(v.assetUrl)+'" target="_blank" rel="noopener">Original video (Drive) ↗</a>':'';}
function changeFor(data,key){
 // Only compare complete, timestamped source observations; never extrapolate today's growth to 24 hours.
 const m=data?.changes24h?.[key];
 const age=Date.now()-Date.parse(m?.at);
 return valid(m)&&m.comparable===true&&age>=0&&age<3*3600000?m:null;
}
function validKitStats(d){
 return d?.version===1&&d.channelId==='cooked-dev'&&Number.isSafeInteger(d.totalSubscribers?.value)&&d.totalSubscribers.value>=0&&Number.isFinite(Date.parse(d.totalSubscribers.at));
}
function kitCard(d,failed=false,scope=selected()?.id||'all',now=Date.now()){
 if(scope!=='all'&&scope!=='cooked-dev')return '';
 const ok=validKitStats(d),m=ok?d.totalSubscribers:null,age=now-Date.parse(m?.at);
 const fresh=ok&&!failed&&d.status==='ok'&&m.method==='kit_api_v4'&&age>=0&&age<30*60000;
 const status=fresh?'Auto-updated · checks target 15 min':!ok?'Waiting for Kit data':failed?'Saved count · feed unavailable':d.status==='authorization_required'?'Connect Kit to enable auto-updates':d.status==='error'?'Saved count · Kit update failed':'Saved count · update overdue';
 const count=m?new Intl.NumberFormat('de-DE').format(m.value):'—';
 return '<article class="stat email-stat"><div class="stat-label">'+svg('<rect x="3" y="5" width="18" height="14" rx="3"/><path d="m3 6 9 7 9-7"/>')+'Emails collected</div><div class="stat-value" tabindex="0" title="Kit Total subscribers · confirmed subscribers">'+count+'</div><p class="kit-owner">Cooked Dev · Kit</p><div class="stat-bottom"><a class="kit-subscribers" href="https://app.kit.com/subscribers" target="_blank" rel="noopener">Subscribers '+svg('<path d="M7 17 17 7M7 7h10v10"/>')+'</a><span class="kit-state '+(fresh?'fresh':'limited')+'" title="'+esc(status)+'">'+(fresh?'Auto-updated':'Saved')+'</span></div></article>';

}
function validLumoKitStats(d){
 return d?.version===1&&d.channelId==='lumo-wins'&&['ok','partial','error','authorization_required'].includes(d.status)
  &&(d.status==='authorization_required'||Number.isFinite(Date.parse(d.lastAttemptAt)));
}
async function fetchKitFeed(filename,validate,previous){
 const urls=['https://raw.githubusercontent.com/Jautis5/cooked-dev-stats/main/site/data/'+filename,'data/'+filename];
 const results=await Promise.allSettled(urls.map(async url=>{
  const response=await fetch(url+'?v='+Date.now(),{cache:'no-store',signal:AbortSignal.timeout(8000)});
  if(!response.ok)throw Error('Kit feed unavailable');
  const data=await response.json();
  if(!validate(data))throw Error('Invalid Kit feed');
  return data;
 }));
 const candidates=results.flatMap(r=>r.status==='fulfilled'?[r.value]:[]);
 const failed=candidates.length===0;
 if(previous)candidates.push(previous);
 const checked=d=>Date.parse(d.lastAttemptAt||d.totalSubscribers?.at)||0;
 return {data:candidates.sort((a,b)=>checked(b)-checked(a))[0]||null,failed};
}
async function loadKit(){
 const [cooked,lumo]=await Promise.all([
  fetchKitFeed('kit.json',validKitStats,kitStats),
  fetchKitFeed('lumo-kit.json',validLumoKitStats,lumoKitStats),
 ]);
 kitFeedFailed=cooked.failed;
 kitStats=cooked.data;
 lumoKitFeedFailed=lumo.failed;
 lumoKitStats=lumo.data;
}
function lumoKitSection(d,failed=false,now=Date.now()){
 const sections=['totalSubscribers','growth','email','forms','broadcasts'];
 const noData=sections.every(key=>d?.[key]?.value==null);
 const delayed=failed||now-Date.parse(d?.lastAttemptAt)>30*60000;
 const state=!d||d.status==='authorization_required'?'Waiting for Kit connection':d.status==='error'?'Kit update failed':d.status==='partial'?'Some Kit metrics could not be refreshed':delayed?'Kit refresh delayed':'Updated '+time(d.lastAttemptAt);
 const head='<div class="block-head"><div><h2 id="lumo-kit-title">Kit newsletter</h2><p class="muted">'+esc(state)+'</p></div><a class="btn" href="https://app.kit.com/dashboard" target="_blank" rel="noopener">Open Kit ↗</a></div>';
 if(noData)return head;
 const value=key=>d?.[key]?.value;
 const observed=key=>d[key]?.at?'Observed '+time(d[key].at):'';
 const checked=key=>observed(key)?' · '+observed(key):'';
 const observedLine=key=>observed(key)?'<p class="muted">'+esc(observed(key))+'</p>':'';
 const number=n=>Number.isFinite(n)?full(n):'—';
 const percent=n=>Number.isFinite(n)?full(n)+'%':'—';
 const period=(a,b)=>esc(String(a||'').slice(0,10)+' – '+String(b||'').slice(0,10));
 const sub=value('totalSubscribers');
 const counts='<p class="muted"><strong>'+number(sub)+'</strong> confirmed subscribers'+esc(checked('totalSubscribers'))+'</p>';
 const table=(title,labels,rows,empty)=>'<h3>'+esc(title)+'</h3>'+(rows.length?'<div class="table-wrap"><table aria-label="'+esc(title)+'"><thead><tr>'+labels.map(label=>'<th scope="col">'+esc(label)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+row.map(cell=>'<td>'+cell+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>':'<p class="muted">'+esc(empty)+'</p>');
 const growth=value('growth');
 const growthTable=table('Subscriber growth',['Period','Dates in Kit','New','Cancellations','Net growth'],[7,30,90].flatMap(days=>{
  const row=growth?.[days];
  return row?[[days+' days',period(row.starting,row.ending),number(row.new_subscribers),number(row.cancellations),number(row.net_new_subscribers)]]:[];
 }),'Growth data unavailable.')+observedLine('growth');
 const email=value('email');
 const emailTable=table('Email performance',['Dates in Kit','Sent','Opened','Open rate','Clicked','Click rate','Unsubscribe rate','Bounce rate'],email?[[period(email.starting,email.ending),number(email.sent),number(email.opened),percent(email.open_rate),number(email.clicked),percent(email.click_rate),percent(email.unsubscribe_rate),percent(email.bounce_rate)]]:[],'Email performance unavailable.')+observedLine('email');
 const forms=value('forms');
 const formTable=table('Signup forms & pages',['Source','Status','Subscribers'],(forms||[]).map(row=>[(row.type==='landing_page'?'Landing page':'Form')+' #'+number(row.id),row.archived?'Archived':'Active',number(row.subscribers)]),forms?'No signup forms or landing pages.':'Signup source data unavailable.')+observedLine('forms');
 const broadcasts=value('broadcasts');
 const broadcastTable=table('Sent broadcasts',['Broadcast','Sent','Recipients','Opens','Open rate','Clicks','Click rate','Unsubscribes','Unsubscribe rate'],(broadcasts||[]).map(row=>['#'+number(row.id),esc(time(row.sentAt)),number(row.recipients),number(row.opens),percent(row.openRate),number(row.clicks),percent(row.clickRate),number(row.unsubscribes),percent(row.unsubscribeRate)]),broadcasts?'No sent broadcasts in the available Kit history.':'Broadcast data unavailable.')+observedLine('broadcasts');
 return head+counts+'<details class="number-notes"><summary>Newsletter analytics</summary>'+growthTable+emailTable+formTable+broadcastTable+'</details>';
}
function renderLumoKit(){
 const section=$('lumo-kit');
 section.hidden=selected()?.id!=='lumo-wins'||currentView()!=='overview';
 if(section.hidden)return;
 const html=lumoKitSection(lumoKitStats,lumoKitFeedFailed);
 if(section.dataset.rendered===html)return;
 section.dataset.rendered=html;
 const wasOpen=section.querySelector('details')?.open;
 section.innerHTML=html;
 if(wasOpen&&section.querySelector('details'))section.querySelector('details').open=true;
}
function renderKit(){
 const stats=$('stats'),html=kitCard(kitStats,kitFeedFailed);
 stats.className='stats'+(html?' has-email-stat':'');stats.innerHTML+=html;
 if($('kit-data-details')){$('kit-data-details').hidden=!html;$('kit-data-details').innerHTML='<h3>Emails collected</h3><p>Cooked Dev · Kit confirmed subscribers</p><p>Updated: '+esc(time(kitStats?.totalSubscribers?.at))+'</p><p>Checks target a fifteen-minute interval, with a 30-minute freshness window. GitHub and Kit can delay updates. Saved values retain their real observation time.</p>';} 
}
function renderStats(s,data){
 const details=[];
 $('stats').innerHTML=[['views','Views'],['likes','Likes'],['followers','Followers'],['posts','Published posts']].map(([key,label])=>{
  const m=s[key],expected=key==='followers'?s.accountCount:s.postCount,partial=key!=='posts'&&m.count<expected,delta=changeFor(data,key);
  const valueTitle=key==='posts'?full(m.value)+' confirmed publication links in the loaded feed':metricTitle(m);
  if(key!=='posts')details.push('<div class="metric-coverage"><strong>'+label+'</strong><span>'+m.count+' / '+expected+(key==='followers'?' accounts':' publications')+'</span><small>Newest: '+esc(time(m.latest||m.oldest))+'<br>Oldest included: '+esc(time(m.oldest))+'</small></div>');
  const note=key==='posts'?s.videoCount+' videos':delta?(delta.value>0?'+':'')+compact(delta.value)+' in 24h':'';
  return '<article class="stat"><div class="stat-label">'+svg(ICONS[key])+label+(partial?'<span class="coverage-indicator" title="Partial coverage. Open Data status for details.">'+svg('<circle cx="12" cy="12" r="9"/><path d="M12 8v5m0 3v.1"/>')+'</span>':'')+'</div><div class="stat-value" title="'+esc(valueTitle)+'" tabindex="0">'+approx(m)+headline(m.value)+'</div><p class="stat-bottom '+(delta?(delta.value<0?'negative':'positive'):'')+'">'+esc(note)+'</p></article>';
 }).join('');
 if($('metric-details'))$('metric-details').innerHTML='<h3>Metric coverage</h3>'+details.join('');
}
function viewHistory(data,now=Date.now()){
 const points=new Map();
 for(const h of data.history||[]){
  const t=Date.parse(h.at);
  if(Number.isFinite(t)&&t<=now&&Number.isFinite(h.views)&&h.views>=0)
   points.set(t,{t,value:h.views,posts:Number.isFinite(h.posts)?h.posts:null,approximate:h.approximate===true});
 }
 const t=Date.parse(data.lastAttemptAt||data.generatedAt),s=summary(data);
 if(Number.isFinite(t)&&t<=now&&valid(s.views))
  points.set(t,{t,value:s.views.value,posts:s.postCount,approximate:s.views.approximate});
 return [...points.values()].sort((a,b)=>a.t-b.t);
}
function combinedViewHistory(datasets,now=Date.now()){
 const series=datasets.map(d=>viewHistory(d,now));
 if(!series.length||series.some(s=>!s.length))return [];
 const times=[...new Set(series.flatMap(s=>s.map(p=>p.t)))].sort((a,b)=>a-b),positions=series.map(()=>-1),out=[];
 for(const t of times){
  series.forEach((s,i)=>{while(positions[i]+1<s.length&&s[positions[i]+1].t<=t)positions[i]++;});
  // A channel with no observation yet is unknown, never an assumed zero.
  if(positions.some(p=>p<0))continue;
  const current=series.map((s,i)=>s[positions[i]]);
  out.push({t,value:current.reduce((n,p)=>n+p.value,0),posts:current.every(p=>Number.isFinite(p.posts))?current.reduce((n,p)=>n+p.posts,0):null,approximate:current.some(p=>p.approximate)});
 }
 return out;
}
function chartWindow(points,range,now=Date.now()){
 const duration={'24h':86400000,'7d':7*86400000,'30d':30*86400000}[range];
 return points.filter(p=>p.t<=now&&(!duration||p.t>=now-duration));
}
function sampleChartPoints(points,limit=160){
 if(points.length<=limit)return points;
 const inner=points.slice(1,-1),buckets=Math.max(1,Math.floor((limit-2)/2)),chosen=new Set([points[0],points[points.length-1]]);
 for(let i=0;i<buckets;i++){
  const group=inner.slice(Math.floor(i*inner.length/buckets),Math.floor((i+1)*inner.length/buckets));
  if(group.length){chosen.add(group.reduce((a,b)=>a.value<b.value?a:b));chosen.add(group.reduce((a,b)=>a.value>b.value?a:b));}
 }
 return [...chosen].sort((a,b)=>a.t-b.t);
}
function chartGeometry(points,width=1000){
 if(!points.length)return null;
 const height=240,left=54,right=18,top=17,bottom=34;
 const low=points.reduce((n,p)=>Math.min(n,p.value),Infinity),high=points.reduce((n,p)=>Math.max(n,p.value),-Infinity);
 const pad=Math.max((high-low)*.16,high*.0005,1),raw=(high-low+2*pad)/4;
 const magnitude=10**Math.floor(Math.log10(raw)),ratio=raw/magnitude;
 const step=Math.max(1,(ratio<=1?1:ratio<=2?2:ratio<=5?5:10)*magnitude);
 const min=Math.max(0,Math.floor((low-pad)/step)*step),max=Math.max(min+step,Math.ceil((high+pad)/step)*step);
 const t0=points[0].t,t1=points[points.length-1].t;
 const coords=points.map(p=>({...p,x:t1===t0?(width+left-right)/2:left+(p.t-t0)/(t1-t0)*(width-left-right),y:top+(max-p.value)/(max-min)*(height-top-bottom)}));
 const ticks=[];for(let n=min;n<=max+step*.01;n+=step)ticks.push({value:n,y:top+(max-n)/(max-min)*(height-top-bottom)});
 return {width,height,left,right,top,bottom,min,max,step,ticks,points:coords};
}
function chartTick(value,step){
 const unit=Math.abs(value)>=1e9?1e9:Math.abs(value)>=1e6?1e6:Math.abs(value)>=1e3?1e3:1;
 const digits=Math.max(0,Math.min(6,Math.ceil(Math.log10(unit/step))));
 return new Intl.NumberFormat('en-US',{minimumFractionDigits:digits,maximumFractionDigits:digits}).format(value/unit)+({1000:'K',1000000:'M',1000000000:'B'}[unit]||'');
}
function chartSeries(config,records,scope,now=Date.now()){
 const chosen=scope==='all'?config:config.filter(c=>c.id===scope);
 const datasets=chosen.map(c=>records.get(c.id)?.data);
 const complete=chosen.length>0&&datasets.every(Boolean);
 return {complete,points:complete?(scope==='all'?combinedViewHistory(datasets,now):viewHistory(datasets[0],now)):[]};
}
function renderViewsChart(){
 const channel=selected(),scope=channel?.id||'all';
 $('views-chart').hidden=false;
 const select=$('chart-channel');
 select.innerHTML='<option value="all">All channels</option>'+channels.map(c=>'<option value="'+esc(c.id)+'">'+esc(c.name)+'</option>').join('');
 select.value=scope;select.hidden=true;
 $('chart-subtitle').textContent=scope==='all'?'Total tracked views across all channels':(channels.find(c=>c.id===scope)?.name||'Channel')+' · all platforms';
 $('views-chart').querySelectorAll('[data-range]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.range===chartRange)));
 const series=chartSeries(channels,entries,scope),complete=series.complete,all=series.points,points=sampleChartPoints(chartWindow(all,chartRange)),latest=points[points.length-1];
 $('chart-total').textContent=latest?(latest.approximate?'≈ ':'')+headline(latest.value):'—';
 $('chart-total').title=latest?full(latest.value)+' recorded views':'';
 $('chart-period').textContent=points.length?new Intl.DateTimeFormat('en-GB',{day:'2-digit',month:'short'}).format(new Date(points[0].t))+' – '+new Intl.DateTimeFormat('en-GB',{day:'2-digit',month:'short'}).format(new Date(latest.t)):'';
 $('chart-history-start').textContent=all.length?'History since '+new Intl.DateTimeFormat('en-GB',{day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',timeZone:'Europe/Vilnius'}).format(new Date(all[0].t))+' · Vilnius time':'';
 $('chart-note').textContent=scope==='all'?'Combined history starts when every channel has a saved observation. Choose a channel to see its earlier history. Totals include rounded or earlier source values.':'Saved observations only. This chart covers all platforms for this channel. Changes can include newly tracked publications; older source values are preserved.';
 if(!points.length){$('chart-plot').innerHTML='<div class="chart-empty">'+(!complete?'Waiting for all channel sources. No estimate is plotted.':all.length?'No saved snapshots in this period. Try a longer range.':'The graph will appear after the first saved views snapshot.')+'</div>';return;}
 const g=chartGeometry(points,Math.max(240,$('chart-plot').clientWidth)),last=g.points[g.points.length-1],floor=g.height-g.bottom;
 const line=g.points.map((p,i)=>(i?'L':'M')+p.x.toFixed(2)+','+p.y.toFixed(2)).join(' ');
 const area=line+' L'+last.x+','+floor+' L'+g.points[0].x+','+floor+' Z';
 const tickCount=g.width<500?3:5,t0=points[0].t,t1=latest.t;
 const xTicks=points.length===1?[{t:t0,x:g.points[0].x}]:Array.from({length:tickCount},(_,i)=>({t:t0+(t1-t0)*i/(tickCount-1),x:g.left+(g.width-g.left-g.right)*i/(tickCount-1)}));
 const tickFormat=new Intl.DateTimeFormat('en-GB',t1-t0>=86400000?{day:'2-digit',month:'short',timeZone:'Europe/Vilnius'}:{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Vilnius'});
 const grid=g.ticks.map(t=>'<line class="chart-grid" x1="'+g.left+'" y1="'+t.y+'" x2="'+(g.width-g.right)+'" y2="'+t.y+'"/><text class="chart-axis" x="'+(g.left-10)+'" y="'+(t.y+4)+'" text-anchor="end">'+chartTick(t.value,g.step)+'</text>').join('');
 const labels=xTicks.map((t,i)=>'<text class="chart-axis" x="'+t.x+'" y="'+(g.height-9)+'" text-anchor="'+(xTicks.length===1?'middle':i===0?'start':i===xTicks.length-1?'end':'middle')+'">'+esc(tickFormat.format(new Date(t.t)))+'</text>').join('');
 const marks=g.points.map((p,i)=>{
  const start=i?(g.points[i-1].x+p.x)/2:g.left,end=i<g.points.length-1?(p.x+g.points[i+1].x)/2:g.width-g.right;
  return '<g class="chart-point" data-point="'+i+'" role="button" tabindex="0" aria-label="'+esc(time(p.t)+', '+(p.approximate?'approximately ':'')+full(p.value)+' recorded views')+'"><rect x="'+start+'" y="'+g.top+'" width="'+Math.max(1,end-start)+'" height="'+(floor-g.top)+'" fill="transparent"/><line class="chart-guide" x1="'+p.x+'" y1="'+g.top+'" x2="'+p.x+'" y2="'+floor+'"/><circle class="chart-dot" cx="'+p.x+'" cy="'+p.y+'" r="3.5"/></g>';
 }).join('');
 $('chart-plot').innerHTML='<svg class="chart-svg" viewBox="0 0 '+g.width+' '+g.height+'" width="100%" height="240" role="group" aria-label="Total tracked views over time"><defs><linearGradient id="views-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#2b9567" stop-opacity=".14"/><stop offset="100%" stop-color="#2b9567" stop-opacity=".01"/></linearGradient></defs>'+grid+(points.length>1?'<path d="'+area+'" fill="url(#views-fill)"/><path d="'+line+'" class="chart-line"/>':'')+labels+marks+'</svg><div class="chart-tooltip" id="chart-tooltip" role="status" hidden></div>';
 function showPoint(i){
  const p=g.points[i],tooltip=$('chart-tooltip');
  $('chart-plot').querySelectorAll('[data-point]').forEach((el,j)=>el.classList.toggle('point-active',i===j));
  tooltip.innerHTML='<strong>'+(p.approximate?'≈ ':'')+full(p.value)+' views</strong><span>'+esc(time(p.t))+'</span>'+(p.posts!=null?'<span>'+p.posts+' tracked publications</span>':'');
  tooltip.style.left=Math.max(0,Math.min(g.width-202,p.x-95))+'px';tooltip.style.top=Math.max(2,p.y-92)+'px';tooltip.hidden=false;
 }
 $('chart-plot').querySelectorAll('[data-point]').forEach((el,i)=>{
  el.addEventListener('pointerenter',()=>showPoint(i));el.addEventListener('focus',()=>showPoint(i));el.addEventListener('click',()=>showPoint(i));
  el.addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();const j=Math.max(0,Math.min(g.points.length-1,i+(e.key==='ArrowRight'?1:-1)));$('chart-plot').querySelector('[data-point="'+j+'"]').focus();}});
 });
}
function scopeHref(id,view='overview'){
 return '#'+(id?'channel/'+encodeURIComponent(id)+(view==='overview'?'':'/'+view):view==='overview'?'':view);
}
function scopedChannels(){const c=selected();return c?[c]:channels;}
function channelBadge(c){return '<span class="scope-badge" data-channel="'+esc(c.id)+'">'+esc(c.name)+'</span>';}
function checkedAt(data){return data?.lastAttemptAt||data?.generatedAt;}
function collectorStatus(health,now=Date.now()){
 if(!health)return {label:'Status unavailable',warning:true};
 if(health.provider!=='GitHub Actions')return {label:'Awaiting first cloud run',warning:true};
 const at=Date.parse(health.completedAt),age=now-at;
 if(!Number.isFinite(age)||age<0||age>45*60000)return {label:'Automatic updates delayed',warning:true};
 if(health.status==='completed_with_gaps')return {label:'Collection ran · coverage incomplete',warning:true};
 if(health.status!=='completed')return {label:'Completed with errors',warning:true};
 const updated=Object.values(health.channels||{}).reduce((n,c)=>n+(c.metricsUpdated||0),0);
 const label=health.initiator==='continuous_clock'?'Automatic collection completed':health.initiator==='watchdog'?'Recovery collection completed':health.trigger==='schedule'?'Scheduled collection completed':health.trigger==='workflow_dispatch'?'On-demand collection completed':'Cloud job completed';
 return {label:updated?label:'Completed · no new metrics',warning:!updated};
}
function renderCloudHealth(){
 const state=collectorStatus(cloudHealth),scope=scopedChannels();
 const records=scope.map(c=>cloudHealth?.channels?.[c.id]).filter(Boolean),count=records.reduce((n,c)=>n+(c.metricsUpdated||0),0);
 const platforms=records.flatMap(c=>Object.values(c.platforms||{})),updated=platforms.filter(p=>p.metricsUpdated>0).length;
 const viewsUpdated=platforms.reduce((n,p)=>n+(p.viewsUpdated||0),0),postsKnown=platforms.reduce((n,p)=>n+(p.postsKnown||0),0);
 $('cloud-health').innerHTML='<div><span class="cloud-label">AUTONOMOUS COLLECTOR</span><strong><span class="dot '+(state.warning?'partial':'ok')+'"></span>'+esc(state.label)+'</strong><small>'+esc(time(cloudHealth?.completedAt))+'</small></div><div><span class="cloud-label">LATEST RUN</span><strong>'+full(count)+' metric observations received</strong><small>'+records.length+' of '+scope.length+' channel reports · observed again does not mean the value changed</small></div><div><span class="cloud-label">VIEWS OBSERVED THIS RUN</span><strong>'+viewsUpdated+' / '+postsKnown+' known posts</strong><small>'+updated+' / '+platforms.length+' accounts supplied any new metric · full inventory checked separately</small></div><div class="cloud-links"><a href="'+safe(cloudHealth?.runUrl||cloudConfig.runsUrl||'https://github.com/Jautis5/cooked-dev-stats/actions/workflows/refresh.yml')+'" target="_blank" rel="noopener">Run details ↗</a><a href="'+safe(cloudConfig.watchdogUrl||'https://github.com/Jautis5/cooked-dev-stats/actions/workflows/watchdog.yml')+'" target="_blank" rel="noopener">Auto-recovery ↗</a><a href="'+safe(cloudConfig.independentUrl||'https://jautis5.github.io/cooked-dev-stats/')+'" target="_blank" rel="noopener">Independent site ↗</a></div>';
}
function clockStatus(runs,now=Date.now()){
 if(!Array.isArray(runs))return {label:'Checking the next cloud update…',warning:true};
 const run=runs.filter(r=>['queued','in_progress','waiting','pending','requested'].includes(r.status)).sort((a,b)=>Date.parse(b.created_at)-Date.parse(a.created_at))[0];
 if(!run)return {label:'Next update is not queued',warning:true};
 const age=now-Date.parse(run.created_at);
 if(!Number.isFinite(age)||age<0||age>20*60000)return {label:'Update queue delayed',warning:true,url:run.html_url};
 if(run.status==='in_progress')return {label:'Checking sources and queuing the next update',warning:false,url:run.html_url};
 return {label:'Next collection attempt queued',warning:false,url:run.html_url,targetAt:Date.parse(run.created_at)+15*60000};
}
function renderClock(){
 const state=clockStatus(clockRuns),target=state.targetAt?' · planned attempt '+time(state.targetAt):'';
 $('cloud-clock').innerHTML='<span><span class="dot '+(state.warning?'partial':'ok')+'"></span><strong>'+esc(state.label)+'</strong>'+esc(target)+'</span><a href="'+safe(state.url||'https://github.com/Jautis5/cooked-dev-stats/actions/workflows/clock.yml')+'" target="_blank" rel="noopener">Timed updates ↗</a>';
}
async function loadClock(){
 try{
  const response=await fetch('https://api.github.com/repos/Jautis5/cooked-dev-stats/actions/workflows/clock.yml/runs?per_page=10',{cache:'no-store',signal:AbortSignal.timeout(8000)});
  if(!response.ok)throw Error('Queue status unavailable');
  const data=await response.json();if(!Array.isArray(data.workflow_runs))throw Error('Invalid queue');
  clockRuns=data.workflow_runs;renderClock();
 }catch{
  $('cloud-clock').innerHTML='<span><span class="dot partial"></span>Queue status unavailable · saved statistics remain visible</span><a href="https://github.com/Jautis5/cooked-dev-stats/actions/workflows/clock.yml" target="_blank" rel="noopener">Timed updates ↗</a>';
 }
}
function sourceState(entry){
 if(!entry?.data)return {label:'Unavailable',warning:true};
 if(entry.fallback)return {label:'Saved snapshot',warning:true};
 if(!Number.isFinite(Date.parse(checkedAt(entry.data)))||Date.now()-Date.parse(checkedAt(entry.data))>45*60000)return {label:'Check overdue',warning:true};
 return {label:entry.data.accounts.some(a=>a.status!=='ok')?'Partial metrics':'Feed checked',warning:entry.data.accounts.some(a=>a.status!=='ok')};
}
function sourceBadge(entry){const s=sourceState(entry);return '<span class="status-badge '+(s.warning?'warning':'')+'"><span class="dot '+(s.warning?'partial':'ok')+'"></span>'+s.label+'</span>';}
function renderNavigation(){
 const c=selected(),view=currentView();
 document.body.dataset.channel=c?.id||'all';
 const icon=document.querySelector('link[rel~="icon"]');if(icon)icon.href=c?.logo||'assets/logo.jpg';
 $('workspace-switcher').innerHTML='<a class="workspace '+(!c?'active':'')+'" href="'+scopeHref(null,view)+'" '+(!c?'aria-current="page"':'')+'><span class="scope-icon" aria-hidden="true">'+svg(NAV_ICONS.overview)+'</span>All channels<span class="workspace-count">'+channels.length+'</span></a>'+channels.map(x=>'<a class="workspace '+(c?.id===x.id?'active':'')+'" data-channel="'+esc(x.id)+'" href="'+scopeHref(x.id,view)+'" '+(c?.id===x.id?'aria-current="page"':'')+'><img src="'+safe(x.logo)+'" alt="">'+esc(x.name)+'</a>').join('');
 const count=scopedChannels().reduce((n,x)=>n+(entries.get(x.id)?.data?.videos.length||0),0);
 $('page-tabs').innerHTML=[['overview','Overview'],['videos','Content library'],['accounts','Connections']].map(([id,label])=>'<a class="page-tab '+(view===id?'active':'')+'" href="'+scopeHref(c?.id,id)+'" '+(view===id?'aria-current="page"':'')+'>'+svg(NAV_ICONS[id])+'<span>'+label+'</span>'+(id==='videos'?'<span class="tab-count">'+count+'</span>':'')+'</a>').join('');
}
function render(){
 const c=selected(),entry=c&&entries.get(c.id),data=entry?.data,view=currentView(),scope=scopedChannels();
 renderedScope=c?.id||'all';
 renderNavigation();renderCloudHealth();renderClock();
 $('channel-logo').hidden=!c;
 if(c){$('channel-logo').src=c.logo;$('channel-logo').alt=c.name;}
 $('page-title').textContent=c?c.name+'.':({overview:'Overview',videos:'Content library',accounts:'Connections'}[view]);
 $('description').textContent=({overview:c?'Your content performance, all in one place.':'Your content at a glance.',videos:'Every video, ready to explore.',accounts:'Your profiles and data sources.'}[view]);
 if($('header-scope'))$('header-scope').textContent=c?.name||'Workspace';
 if($('header-view'))$('header-view').textContent=({overview:'Overview',videos:'Content library',accounts:'Connections'}[view]);
 if($('scope-label'))$('scope-label').textContent=c?c.name:channels.length+' channels';
 document.title=(c?c.name:'All channels')+' · '+({overview:'Overview',videos:'Video tracker',accounts:'Accounts & sources'}[view])+' · Social Stats';
 $('stats').hidden=view!=='overview';
 if($('workspace-error'))$('workspace-error').hidden=true;
 $('overview-section').hidden=view!=='overview';$('video-section').hidden=view!=='videos';$('accounts-section').hidden=view!=='accounts';
 $('channels-section').hidden=!!c;$('comparison-section').hidden=!!c;$('channel-section').hidden=!c||!data;
 $('sheet-link').href=c?.sheetUrl||'#';$('sheet-link').hidden=!c?.sheetUrl;
 $('library-link').href=c?.assetLibraryUrl||'#';$('library-link').hidden=!c?.assetLibraryUrl;
 const plan=c?.publishingPlan,planBox=$('publishing-plan');
 planBox.hidden=!plan||view!=='overview';
 if(plan)planBox.innerHTML='<div><h2>3 episodes a week · US first</h2><p>Tue · Thu · Sun at 6:00 PM New York time. '+esc(plan.voteWindowHours)+' hours for the Instagram vote.</p><p class="muted">Instagram Reels → TikTok · YouTube Shorts · Facebook Reels · X.</p><p class="publishing-status">No posts scheduled. Automatic publishing is not connected.</p></div><a class="btn" href="'+safe(c.assetLibraryUrl)+'" target="_blank" rel="noopener">Open video source ↗</a>';

 const available=scope.filter(x=>entries.get(x.id)?.data),summaries=available.map(x=>summary(entries.get(x.id).data));
 if(available.length)renderStats(combine(summaries),data||(available.length===1?entries.get(available[0].id).data:null));
 else $('stats').innerHTML='<p class="loading">Stats are unavailable. Try reloading the feed.</p>';
 renderKit();
 renderLumoKit();
 const attempts=scope.map(x=>checkedAt(entries.get(x.id)?.data)).filter(Boolean).sort();
 $('last-check').textContent=attempts.length?(c?'Feed checked: ':'Oldest feed check: ')+time(attempts[0]):'No successful feed check';
 const states=scope.map(x=>sourceState(entries.get(x.id)));
 $('refresh-dot').className='dot '+(states.some(s=>s.warning)?'partial':'ok');
 const failed=scope.filter(x=>!entries.get(x.id)?.data),fallback=scope.filter(x=>entries.get(x.id)?.fallback),problems=[];
 if(failed.length)problems.push(failed.map(x=>x.name).join(', ')+': source unavailable. Shared totals exclude these channels.');
 const catchingUp=fallback.filter(x=>entries.get(x.id)?.fallbackReason==='newer_snapshot'),unreachable=fallback.filter(x=>entries.get(x.id)?.fallbackReason!=='newer_snapshot');
 if(catchingUp.length)problems.push(catchingUp.map(x=>x.name).join(', ')+': live feed is catching up; showing a newer verified snapshot.');
 if(unreachable.length)problems.push(unreachable.map(x=>x.name).join(', ')+': live feed unavailable; showing the last saved snapshot.');
 if(scope.some(x=>{const at=checkedAt(entries.get(x.id)?.data);return at&&Date.now()-Date.parse(at)>45*60000;}))problems.push('Automatic collection is delayed; showing the last saved observations. Reload saved stats checks for already collected data. See Accounts & sources for exact metric times.');
 if(data?.tracking?.note)problems.push(data.tracking.note);
 $('notice').textContent=problems.join(' ');$('notice').hidden=!problems.length;
 if(view==='overview'){
  if(c&&data)renderChannel(c,data);else renderChannels();
  if(!c)renderComparison();
  renderAttention();renderViewsChart();renderTopContent();
 }else if(view==='videos'){renderVideoFilters();renderVideos();renderResources();}
 else renderAccounts();
}
function renderChannels(){
 $('channel-count').textContent=channels.length;
 $('channels').innerHTML=channels.map(c=>{
  const entry=entries.get(c.id),d=entry?.data,s=d&&summary(d);
  return '<a class="channel-row" data-channel="'+esc(c.id)+'" href="'+scopeHref(c.id)+'"><img class="channel-logo" src="'+safe(c.logo)+'" alt=""><span class="channel-identity"><strong>'+esc(c.name)+'</strong><small>'+(s?s.videoCount+' videos':'Source unavailable')+'</small></span><span class="channel-result" title="'+esc(metricTitle(s?.views))+'">'+approx(s?.views)+headline(s?.views?.value)+'<small>views</small></span>'+svg('<path d="m9 6 6 6-6 6"/>','channel-chevron')+'</a>';
 }).join('');
}
function renderTopContent(){
 const host=$('top-content');if(!host)return;
 const rows=collectVideoRows(scopedChannels(),entries).filter(r=>valid(total(Object.values(r.video.posts),'views'))).sort((a,b)=>total(Object.values(b.video.posts),'views').value-total(Object.values(a.video.posts),'views').value).slice(0,4);
 $('top-content-link').href=scopeHref(selected()?.id,'videos');
 host.innerHTML=rows.length?rows.map((r,i)=>{
  const v=r.video,m=total(Object.values(v.posts),'views');
  return '<button class="content-card" data-top-row="'+i+'"><span class="content-image">'+(v.thumbnail?'<img src="'+safe(v.thumbnail)+'" alt="" loading="lazy">':'<img class="content-avatar" src="'+safe(r.channel.logo)+'" alt="">')+'<span class="content-play">'+svg('<path d="m9 6 9 6-9 6Z"/>')+'</span><span class="content-platforms">'+Object.keys(v.posts).map(p=>ABBR[p]||p).join(' · ')+'</span></span><span class="content-card-body"><span class="content-channel"><img src="'+safe(r.channel.logo)+'" alt="">'+esc(r.channel.name)+'</span><strong class="content-caption">'+esc(videoTitle(v))+'</strong><span class="content-performance"><span>'+svg(ICONS.views)+approx(m)+headline(m.value)+' views</span>'+svg('<path d="M7 17 17 7M7 7h10v10"/>')+'</span></span></button>';
 }).join(''):'<div class="empty"><strong>Your content will appear here.</strong>Confirmed posts with measured views are shown automatically.</div>';
 host.querySelectorAll('[data-top-row]').forEach(button=>button.addEventListener('click',()=>{const r=rows[Number(button.dataset.topRow)];detail(r.channel.id,r.video.id);}));
}
function renderComparison(){
 $('comparison-rows').innerHTML=channels.map(c=>{
  const entry=entries.get(c.id),data=entry?.data,s=data&&summary(data);
  return '<tr><td><a class="table-channel" href="'+scopeHref(c.id)+'"><img src="'+safe(c.logo)+'" alt="">'+esc(c.name)+'</a></td>'+['views','likes','followers'].map(k=>'<td class="number">'+metricCell(s?.[k],false)+'</td>').join('')+'<td class="number">'+(s?s.videoCount:'—')+'</td><td class="number">'+(s?s.postCount:'—')+'</td><td>'+sourceBadge(entry)+'<span class="tiny">'+esc(time(checkedAt(data)))+'</span></td></tr>';
 }).join('');
}
function platformSummary(data,a){return summary(data,a.id);}
function inventoryAudit(data,account,now=Date.now()){
 if(!collectionActive(account))return {at:null,overdue:false,complete:false,retired:true};
 const report=data.discovery?.[account.id]||{},at=report.complete?report.checkedAt:report.lastCompleteAt;
 const age=now-Date.parse(at),overdue=!Number.isFinite(age)||age>2*3600000;
 return {at,overdue,complete:report.complete===true&&!overdue};
}
function accountState(data,a,now=Date.now()){
 if(!collectionActive(a))return {label:'Deleted account · history retained',warning:false};
 const inventory=inventoryAudit(data,a,now);
 if(inventory.overdue)return {label:'New-video check overdue',warning:true};
 if(!inventory.complete)return {label:'Full list recently checked',warning:true};
 return {label:a.status==='ok'?'Checked':a.status==='partial'?'Partial metrics':'Source limited',warning:a.status!=='ok'};
}
function renderChannel(c,data){
 $('platforms').innerHTML=data.accounts.map(a=>{
  const s=platformSummary(data,a),state=accountState(data,a);
  return '<button class="platform" data-platform="'+esc(a.id)+'" aria-label="View '+esc(a.name)+' video tracking"><div class="platform-head"><span class="platform-name">'+esc(a.name)+'</span><span class="sub">'+s.postCount+' posts ↗</span></div><div class="big" title="'+esc(metricTitle(s.views))+'">'+approx(s.views)+compact(s.views.value)+'</div><div class="sub">views · '+compact(a.metrics?.followers?.value)+' followers</div><div class="status" title="'+esc(statusText(a))+'"><span class="dot '+(state.warning?'partial':'ok')+'"></span>'+esc(state.label)+'</div></button>';
 }).join('');
 $('platforms').querySelectorAll('[data-platform]').forEach(b=>b.addEventListener('click',()=>{active=b.dataset.platform;location.hash=scopeHref(c.id,'videos');}));
 $('channel-accounts-link').href=scopeHref(c.id,'accounts');
 $('channel-links').innerHTML=data.accounts.map(a=>'<a href="'+safe(a.url)+'" target="_blank" rel="noopener">'+esc(a.name)+' ↗</a>').join('')+(c.assetLibraryUrl?'<a href="'+safe(c.assetLibraryUrl)+'" target="_blank" rel="noopener">Video library ↗</a>':'');
}
function issuesFor(config,records){
 const issues=[];
 for(const c of config){
  const e=records.get(c.id),d=e?.data;
  if(!d){issues.push({channel:c,title:'Feed unavailable',text:'This channel is excluded from shared totals until a source can be loaded.'});continue;}
  if(e.fallback)issues.push({channel:c,title:'Saved snapshot in use',text:'The live feed could not be reached. The last verified observations are preserved.'});
  const blocked=d.accounts.filter(a=>collectionActive(a)&&['unavailable','snapshot'].includes(a.status));
  if(blocked.length)issues.push({channel:c,title:'Source access needs a check',text:blocked.map(a=>a.name).join(', ')+': current collection is limited. Earlier metric values may still be visible.'});
  const overdue=d.accounts.filter(a=>inventoryAudit(d,a).overdue);
  if(overdue.length)issues.push({channel:c,title:'New-video discovery overdue',text:overdue.map(a=>a.name).join(', ')+': no complete publication list verified within 2 hours. Metric refreshes cannot confirm that new videos were found.'});
  const posts=d.videos.flatMap(v=>Object.values(v.posts)),missing=posts.filter(p=>!valid(p.metrics?.views)).length;
  if(missing)issues.push({channel:c,title:missing+' posts have no view count',text:'These are confirmed publications with an unavailable view metric. Shared views include only known values.'});
  if(d.accounts.some(a=>a.status==='partial'))issues.push({channel:c,title:'Some metrics have different update times',text:'A successful feed check does not refresh every metric. Check the observation times before comparing growth.'});
  if(!d.videos.length)issues.push({channel:c,title:'No tracked video publications yet',text:d.tracking?.note||'This feed has no confirmed video publications. Open this channel’s source library to see its original files.'});
 }
 return issues;
}
function renderAttention(){
 const scope=scopedChannels(),issues=issuesFor(scope,entries);
 $('attention-accounts-link').href=scopeHref(selected()?.id,'accounts');
 $('attention-list').innerHTML=issues.length?issues.map(i=>'<div class="attention-item"><div><strong>'+channelBadge(i.channel)+esc(i.title)+'</strong><p>'+esc(i.text)+'</p></div><a href="'+scopeHref(i.channel.id,'accounts')+'">Check sources ↗</a></div>').join(''):'<div class="attention-item"><div><strong>No source issues detected</strong><p>Each metric still keeps its own observation time.</p></div></div>';
}
function collectVideoRows(config,records){
 return config.flatMap(channel=>{const data=records.get(channel.id)?.data;return data?data.videos.map(video=>({channel,data,video})):[];});
}
function coverageFor(row,platform='all'){
 const accounts=row.data.accounts.filter(a=>platform==='all'||a.id===platform);
 const confirmed=accounts.filter(a=>row.video.posts[a.id]?.url).length;
 return {confirmed,total:accounts.length,gaps:accounts.length-confirmed};
}
function postsFor(v,platform=active){return Object.entries(v.posts).filter(([p])=>platform==='all'||p===platform).map(([,p])=>p);}
function filterVideoRows(rows,{term='',channel='all',platform='all',coverage='all',sort='views'}={}){
 term=term.trim().toLowerCase();
 const list=rows.filter(r=>{
  if(channel!=='all'&&r.channel.id!==channel)return false;
  if(!r.data.accounts.some(a=>platform==='all'||a.id===platform))return false;
  if(term&&!(videoTitle(r.video)+' '+r.channel.name).toLowerCase().includes(term))return false;
  const count=coverageFor(r,platform);
  return coverage==='gaps'?count.gaps>0:coverage==='complete'?count.total>0&&count.gaps===0:true;
 });
 const stamp=v=>{const value=Date.parse(v.publishedAt);return Number.isFinite(value)?value:0;};
 return list.sort((a,b)=>sort==='recent'?stamp(b.video)-stamp(a.video):sort==='gaps'?coverageFor(b,platform).gaps-coverageFor(a,platform).gaps:(total(postsFor(b.video,platform),sort).value??-1)-(total(postsFor(a.video,platform),sort).value??-1));
}
function trackerOptions(){return {term:$('search').value,channel:selected()?.id||$('video-channel').value,platform:active,coverage:$('video-coverage').value,sort:$('sort').value};}
function visibleVideoRows(){return filterVideoRows(collectVideoRows(scopedChannels(),entries),trackerOptions());}
function renderVideoFilters(){
 const scope=scopedChannels(),previous=$('video-channel').value;
 $('video-channel').innerHTML='<option value="all">All channels</option>'+channels.map(c=>'<option value="'+esc(c.id)+'">'+esc(c.name)+'</option>').join('');
 $('video-channel').value=selected()?.id||(channels.some(c=>c.id===previous)?previous:'all');
 $('video-channel').parentElement.hidden=!!selected();
 const accounts=[...new Map(scope.flatMap(c=>entries.get(c.id)?.data?.accounts||[]).map(a=>[a.id,a])).values()];
 if(!accounts.some(a=>a.id===active))active='all';
 $('video-platform').innerHTML='<option value="all">All platforms</option>'+accounts.map(a=>'<option value="'+esc(a.id)+'">'+esc(a.name)+'</option>').join('');
 $('video-platform').value=active;
}
function renderVideos(){
 renderSchedule();
 const vs=visibleVideoRows(),scope=scopedChannels(),allCount=collectVideoRows(scope,entries).length,opts=trackerOptions();
 $('video-count').textContent='('+vs.length+' of '+allCount+')';
 const channelName=channels.find(c=>c.id===opts.channel)?.name||'All channels',platformName=active==='all'?'All platforms':ABBR[active]||active;
 $('active-filter').textContent=channelName+' · '+platformName+' · '+vs.reduce((n,r)=>n+coverageFor(r,active).confirmed,0)+' confirmed posts shown';
 $('clear-filter').hidden=!opts.term&&active==='all'&&opts.coverage==='all'&&(selected()||opts.channel==='all')&&opts.sort==='views';
 $('videos').innerHTML=vs.map((r,i)=>{
  const v=r.video,count=coverageFor(r),date=Date.parse(v.publishedAt);
  return '<tr><td><div class="video-info">'+(v.thumbnail?'<img class="thumb" src="'+safe(v.thumbnail)+'" alt="" loading="lazy" onerror="this.hidden=true">':'<span class="thumb" aria-hidden="true"></span>')+'<div><button class="video-title" data-row="'+i+'">'+esc(videoTitle(v))+'</button><div class="video-meta">'+channelBadge(r.channel)+(Number.isFinite(date)?'<time datetime="'+esc(v.publishedAt)+'">'+esc(new Intl.DateTimeFormat('en-GB',{day:'2-digit',month:'short',timeZone:'Europe/Vilnius'}).format(new Date(date)))+'</time>':'')+'</div>'+assetLink(v)+'</div></div></td><td><div class="post-links">'+r.data.accounts.map(a=>{const p=v.posts[a.id];return p?.url?'<a class="post-link" href="'+safe(p.url)+'" target="_blank" rel="noopener" title="'+esc(a.name)+' · confirmed post">'+esc(ABBR[a.id]||a.name)+' ↗</a>':missingPublication(a,r.data);}).join('')+'</div><p class="coverage-caption">'+count.confirmed+' / '+count.total+' platforms confirmed</p></td>'+['views','likes','comments','shares'].map(k=>'<td class="number">'+metricCell(total(postsFor(v),k))+'</td>').join('')+'</tr>';
 }).join('');
 $('videos').querySelectorAll('[data-row]').forEach(b=>b.addEventListener('click',()=>{const r=vs[Number(b.dataset.row)];detail(r.channel.id,r.video.id);}));
 $('empty').hidden=vs.length>0;
 $('empty').innerHTML=allCount?'<strong>No videos match these filters.</strong>Try another channel, platform or search.':'<strong>No tracked video publications yet.</strong>Original files are available through the channel library below. Publications appear here after they are confirmed in the source feed.';
 $('export-csv').disabled=!vs.length;
}
function renderResources(){
 $('video-resources').innerHTML=scopedChannels().map(c=>'<article class="resource-card"><h3>'+esc(c.name)+' · source files & tracking</h3>'+(c.assetLibraryUrl?'<a href="'+safe(c.assetLibraryUrl)+'" target="_blank" rel="noopener">Open video library ↗</a>':'')+(c.sheetUrl?'<a href="'+safe(c.sheetUrl)+'" target="_blank" rel="noopener">Open channel Sheet ↗</a>':'')+'<p>Original files and publication records are separate. A file in Drive is not a confirmed post.</p></article>').join('');
}
function scheduleState(post,now=Date.now()){
 if(!post)return {label:'Not scheduled',warning:true};
 if(post.status==='scheduled'){
  const at=Date.parse(post.scheduledAt);
  if(!Number.isFinite(at))return {label:'Verify saved time',warning:true};
  return at<=now?{label:'Due · verify publication',warning:true}:{label:'Scheduled',warning:false};
 }
 return {label:post.status==='save_submitted'?'Verify saved schedule':post.status==='awaiting_original'?'Waiting for original':'Not scheduled',warning:true};
}
function renderSchedule(){
 const block=$('schedule-block');
 if(!block)return;
 const ids=scopedChannels().map(c=>c.id);
 block.hidden=!publishingQueue||!ids.includes(publishingQueue.channelId);
 if($('schedule-disclosure'))$('schedule-disclosure').hidden=block.hidden;
 if(block.hidden)return;
 const q=publishingQueue,scheduled=q.items.flatMap(v=>Object.values(v.posts)).filter(p=>p.status==='scheduled').length;
 $('schedule-summary').textContent=q.items.length+' source videos · '+scheduled+' confirmed saved schedules · target: 2 videos per day per platform · Vilnius time';
 $('schedule-note').textContent='Checked '+time(q.updatedAt)+'. Scheduled videos are excluded from published counts and performance totals. '+(q.missingAssets?.length?'Waiting for original: '+q.missingAssets.map(v=>v.caption).join(', '):'');
 $('schedule-rows').innerHTML=q.items.map(v=>'<tr><td><strong>'+esc(v.caption)+'</strong><div class="tiny"><a href="'+safe(v.assetUrl)+'" target="_blank" rel="noopener">'+esc(v.filename)+' ↗</a></div></td>'+['youtube','x','facebook'].map(p=>{
  const post=v.posts[p],state=scheduleState(post);
  return '<td><span class="status-badge '+(state.warning?'warning':'')+'">'+esc(state.label)+'</span><div class="tiny">'+(post?.status==='pending'?'Planned: ':'')+(post?.scheduledAt?esc(time(post.scheduledAt)):esc(post?.scheduledLocal||'No saved date'))+'</div>'+(post?.url&&post.status!=='pending'?'<a class="tiny" href="'+safe(post.url)+'" target="_blank" rel="noopener">Open '+(p==='youtube'?'video':'queue')+' ↗</a>':'')+'</td>';
 }).join('')+'</tr>').join('');
}
function accountHandle(a){const handle=a.expectedHandle||a.handle;return handle?(/\s/.test(handle)?handle:'@'+handle):a.expectedPageId?'Page '+a.expectedPageId:a.expectedChannelId?'Channel '+a.expectedChannelId:'Profile linked below';}
function inventoryText(data,account,now=Date.now()){
 if(!collectionActive(account))return 'Collection stopped after owner confirmation on '+time(account.collection.reportedAt)+'. Awaiting a separately confirmed replacement account.';
 const report=data.discovery?.[account.id],known=data.videos.filter(v=>v.posts[account.id]).length;
 const expected=account.metrics?.publishedCount;
 const gap=valid(expected)&&expected.value>known?' · profile reported '+expected.value+' posts; '+known+' linked':'';
 const inventory=inventoryAudit(data,account,now);
 const label=inventory.overdue?'New-video discovery overdue':inventory.complete?'Complete list verified':'Full list verified recently · latest source check was partial';
 return label+gap+(report?.lastCompleteAt?' · last full list: '+time(report.lastCompleteAt):'');
}
function renderAccounts(){
 $('account-groups').innerHTML=scopedChannels().map(c=>{
  const entry=entries.get(c.id),d=entry?.data;
  return '<article class="account-group"><div class="account-group-head"><img src="'+safe(c.logo)+'" alt=""><div><h3>'+esc(c.name)+'</h3><p>'+esc(time(checkedAt(d)))+' · feed check</p></div><a href="'+scopeHref(c.id)+'">Overview ↗</a></div>'+(d?d.accounts.map(a=>{
   const s=platformSummary(d,a),state=accountState(d,a);
   return '<div class="account-row"><div class="account-row-top"><div><a class="account-name" href="'+safe(a.url)+'" target="_blank" rel="noopener">'+esc(a.name)+' ↗</a><p class="account-handle">'+esc(accountHandle(a))+'</p></div><span class="status-badge '+(state.warning?'warning':'')+'"><span class="dot '+(state.warning?'partial':'ok')+'"></span>'+esc(state.label)+'</span></div><div class="account-metrics"><div><strong>'+metricCell(a.metrics?.followers,false)+'</strong><small>Followers</small></div><div><strong>'+metricCell(s.views,false)+'</strong><small>Tracked views</small></div><div><strong>'+s.postCount+'</strong><small>Confirmed video posts</small></div></div><p class="account-check">Source check: '+esc(time(a.lastAttemptAt))+' · followers observed: '+esc(time(a.metrics?.followers?.at))+' · oldest views: '+esc(time(s.views.oldest))+'</p><p class="account-note">'+esc(inventoryText(d,a))+'</p><p class="account-note">'+esc(statusText(a))+'</p></div>';
  }).join(''):'<p class="empty">Source unavailable. No values are assumed.</p>')+(d?.tracking?.note?'<p class="account-scope-note">'+esc(d.tracking.note)+'</p>':'')+'<div class="account-resources">'+(c.assetLibraryUrl?'<a href="'+safe(c.assetLibraryUrl)+'" target="_blank" rel="noopener">Video library ↗</a>':'')+(c.sheetUrl?'<a href="'+safe(c.sheetUrl)+'" target="_blank" rel="noopener">Channel Sheet ↗</a>':'')+'<a href="'+safe(c.dataUrl)+'" target="_blank" rel="noopener">Source data ↗</a></div></article>';
 }).join('');
}
function detail(channelId,id){
 const c=channels.find(x=>x.id===channelId),data=entries.get(channelId)?.data,v=data?.videos.find(v=>v.id===id);if(!v)return;
 $('detail-channel').textContent=c.name;$('detail-title').textContent=videoTitle(v);$('detail-caption').textContent='';$('detail-caption').hidden=true;$('detail-original').innerHTML=assetLink(v);
 $('detail-rows').innerHTML=data.accounts.map(a=>{const p=v.posts[a.id];return '<tr><td>'+(p?.url?'<a href="'+safe(p.url)+'" target="_blank" rel="noopener">'+esc(a.name)+' ↗</a><span class="tiny">Confirmed publication</span>':esc(a.name)+'<span class="tiny">Publication not confirmed</span>')+'</td>'+['views','likes','comments','shares'].map(k=>'<td class="number">'+metricCell(p?.metrics?.[k],true)+'</td>').join('')+'</tr>';}).join('');
 $('detail').showModal();
}
function csvCell(value){
 const s=String(value??'');
 // Prevent source captions from executing as formulas when opened in a spreadsheet.
 return '"'+(/^[\s]*[=+@-]/.test(s)?"'":'')+s.replace(/"/g,'""')+'"';
}
function videoCsv(rows,platform='all'){
 const fields=['Channel','Video','Platform','Publication status','Post URL','Original URL','Views','Views observed at','Views approximate','Likes','Likes observed at','Comments','Comments observed at','Shares','Shares observed at'];
 const lines=[fields];
 for(const r of rows)for(const a of r.data.accounts.filter(a=>platform==='all'||a.id===platform)){
  const p=r.video.posts[a.id],ms=p?.metrics;
  lines.push([r.channel.name,videoTitle(r.video),a.name,p?.url?'Confirmed':'Not confirmed',p?.url||'',r.video.assetUrl||'',ms?.views?.value,ms?.views?.at,valid(ms?.views)?!!ms.views.approximate:'',ms?.likes?.value,ms?.likes?.at,ms?.comments?.value,ms?.comments?.at,ms?.shares?.value,ms?.shares?.at]);
 }
 return '\uFEFF'+lines.map(row=>row.map(csvCell).join(',')).join('\r\n');
}
function toast(message){$('toast').textContent=message;$('toast').classList.add('show');setTimeout(()=>$('toast').classList.remove('show'),2500);}
function resetTracker(){active='all';$('search').value='';$('video-channel').value=selected()?.id||'all';$('video-platform').value='all';$('video-coverage').value='all';$('sort').value='views';renderVideos();}
function newestSnapshot(candidates){
 return candidates.filter(c=>c.data).sort((a,b)=>(Date.parse(checkedAt(b.data))||0)-(Date.parse(checkedAt(a.data))||0)||Number(a.fallback)-Number(b.fallback))[0]||null;
}
function newestHealth(candidates){
 const valid=candidates.filter(h=>h?.version===1&&h.channels&&Number.isFinite(Date.parse(h.completedAt)));
 const cloud=valid.filter(h=>h.provider==='GitHub Actions');
 return (cloud.length?cloud:valid).sort((a,b)=>Date.parse(b.completedAt)-Date.parse(a.completedAt))[0]||null;
}
async function fetchData(url,refresh=false){
 const u=new URL(url,location.href);u.searchParams.set('v',String(Date.now()));
 const r=await fetch(u,{cache:'no-store',signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error('Source unavailable');
 const d=await r.json();if(d.version!==1||!Array.isArray(d.accounts)||!Array.isArray(d.videos))throw Error('Invalid stats');return d;
}
async function loadRegistry(){
 const r=await fetch('data/channels.json?v='+Date.now(),{cache:'no-store',signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error('Channel list unavailable');
 const config=await r.json();if(config.version!==1||!Array.isArray(config.channels))throw Error('Invalid channels');
 channels=config.channels;cloudConfig=config.collector||{};
}
async function load(manual=false){
 if(loading)return;loading=true;$('reload').disabled=true;
 try{
  try{await loadRegistry();}catch(error){if(!channels.length)throw error;}
  const kitTask=loadKit();
  const healthTask=(async()=>{
   const urls=[cloudConfig.healthUrl||'https://raw.githubusercontent.com/Jautis5/cooked-dev-stats/main/data/health.json','data/health.json'];
   const results=await Promise.allSettled(urls.map(async url=>{const r=await fetch(url+'?v='+Date.now(),{cache:'no-store',signal:AbortSignal.timeout(8000)});if(!r.ok)throw Error('Health unavailable');return r.json();}));
   cloudHealth=newestHealth([...results.flatMap(r=>r.status==='fulfilled'?[r.value]:[]),...(cloudHealth?[cloudHealth]:[])]);
  })();
  const scheduleTask=(async()=>{
   try{const r=await fetch('data/schedules.json?v='+Date.now(),{cache:'no-store',signal:AbortSignal.timeout(8000)});if(!r.ok)return;const q=await r.json();if(q.version===1&&Array.isArray(q.items))publishingQueue=q;}catch{}
  })();
  await Promise.all(channels.map(async c=>{
   const previous=entries.get(c.id),results=await Promise.allSettled([fetchData(c.dataUrl,manual),fetchData(c.fallbackUrl,manual)]);
   const candidates=results.flatMap((r,i)=>r.status==='fulfilled'?[{data:r.value,fallback:i===1}]:[]);
   if(previous?.data)candidates.push({...previous,fallback:true});
   const chosen=newestSnapshot(candidates);
   if(chosen){chosen.fallbackReason=chosen.fallback&&results[0].status==='fulfilled'?'newer_snapshot':'unreachable';entries.set(c.id,chosen);}
   else entries.set(c.id,{data:null,fallback:true});
  }));
  await Promise.all([healthTask,scheduleTask,kitTask]);render();void loadClock();
 }catch{
  const message='Could not load your workspace. Use Refresh to try again.';
  $('notice').textContent=message;$('notice').hidden=false;
  if(!entries.size){$('stats').innerHTML='<div class="empty"><strong>Could not load your workspace.</strong>Use Refresh to try again.</div>';if($('workspace-error')){$('workspace-error').textContent=message;$('workspace-error').hidden=false;}}
 }
 finally{loading=false;$('reload').disabled=false;}
}
function closeNavigation(){
 document.body.classList?.remove('navigation-open');
 $('menu-toggle')?.setAttribute('aria-expanded','false');
 if($('sidebar-backdrop'))$('sidebar-backdrop').hidden=true;
 const rail=$('sidebar');
 if(rail){rail.removeAttribute?.('role');rail.removeAttribute?.('aria-modal');rail.inert=typeof matchMedia==='function'&&matchMedia('(max-width:900px)').matches;}
 if($('main'))$('main').inert=false;
}
window.addEventListener('hashchange',()=>{
 const fromDrawer=document.body.classList?.contains('navigation-open');
 closeNavigation();
 if((selected()?.id||'all')!==renderedScope){active='all';$('search').value='';$('video-channel').value='all';$('video-coverage').value='all';$('sort').value='views';}
 render();if(fromDrawer)$('page-title')?.focus?.({preventScroll:true});window.scrollTo({top:0,behavior:'instant'});
});
$('views-chart').querySelectorAll('[data-range]').forEach(b=>b.addEventListener('click',()=>{chartRange=b.dataset.range;renderViewsChart();}));
$('chart-plot').addEventListener('pointerleave',()=>{const t=$('chart-tooltip');if(t)t.hidden=true;$('chart-plot').querySelectorAll('.point-active').forEach(el=>el.classList.remove('point-active'));});
if(typeof ResizeObserver!=='undefined')new ResizeObserver(()=>{if(entries.size&&currentView()==='overview')renderViewsChart();}).observe($('chart-plot'));
$('search').addEventListener('input',renderVideos);
for(const id of ['sort','video-channel','video-coverage'])$(id).addEventListener('change',renderVideos);
$('video-platform').addEventListener('change',e=>{active=e.target.value;renderVideos();});
$('clear-filter').addEventListener('click',resetTracker);
$('reload').addEventListener('click',()=>load(true));
$('close-modal').addEventListener('click',()=>$('detail').close());
$('detail').addEventListener('click',e=>{if(e.target===$('detail'))$('detail').close();});
$('share').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(location.href);toast('Link copied');}catch{toast('Copy this page’s address to share this exact view.');}});
$('export-csv').addEventListener('click',()=>{
 const url=URL.createObjectURL(new Blob([videoCsv(visibleVideoRows(),active)],{type:'text/csv;charset=utf-8'}));
 const link=document.createElement('a');link.href=url;link.download='social-stats-'+(selected()?.id||'all-channels')+'-'+new Date().toISOString().slice(0,10)+'.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 toast('Filtered publication tracker exported');
});
$('menu-toggle')?.addEventListener('click',()=>{const open=document.body.classList.toggle('navigation-open');$('menu-toggle').setAttribute('aria-expanded',String(open));$('sidebar-backdrop').hidden=!open;const rail=$('sidebar');rail.inert=false;rail.setAttribute('role',open?'dialog':'navigation');rail.setAttribute('aria-modal',String(open));$('main').inert=open;if(open)$('menu-close').focus();});
$('sidebar-backdrop')?.addEventListener('click',()=>{closeNavigation();$('menu-toggle').focus();});
$('menu-close')?.addEventListener('click',()=>{closeNavigation();$('menu-toggle').focus();});
document.addEventListener('keydown',event=>{if(event.key==='Escape'){const wasOpen=document.body.classList.contains('navigation-open');closeNavigation();if($('data-status'))$('data-status').open=false;if(wasOpen)$('menu-toggle').focus();}if(event.key==='Tab'&&document.body.classList.contains('navigation-open')){const items=[...$('sidebar').querySelectorAll('a,button')].filter(e=>e.getClientRects().length),first=items[0],last=items.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}});
function syncNavigation(){const mobile=matchMedia('(max-width:900px)').matches;$('sidebar').inert=mobile&&!document.body.classList.contains('navigation-open');if(!mobile)closeNavigation();}
syncNavigation();window.addEventListener('resize',syncNavigation);
$('sidebar')?.addEventListener('click',event=>{const link=event.target.closest('a');if(link&&new URL(link.href).hash===location.hash&&document.body.classList.contains('navigation-open')){closeNavigation();$('page-title').focus({preventScroll:true});}});
document.querySelector('.skip-link')?.addEventListener('click',event=>{event.preventDefault();$('main').focus();});

load();setInterval(load,300000);
setInterval(async()=>{await loadKit();renderLumoKit();const email=$('stats').querySelector('.email-stat');if(email){const node=document.createElement('div');node.innerHTML=kitCard(kitStats,kitFeedFailed);email.replaceWith(node.firstElementChild);}},60000);
