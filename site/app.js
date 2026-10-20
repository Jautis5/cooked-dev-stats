'use strict';
const $ = id => document.getElementById(id);
const ABBR = {instagram:'IG',tiktok:'TT',youtube:'YT',x:'X',facebook:'FB'};
const ICONS = {
 views:'<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
 likes:'<path d="M7 10h-4v11h4zm0 11h11a2 2 0 0 0 2-1.6l1.3-7A2 2 0 0 0 19.3 10H14l1-5a2.5 2.5 0 0 0-3-2L7 10Z"/>',
 followers:'<circle cx="9" cy="8" r="3.5"/><path d="M2 21v-2a7 7 0 0 1 14 0v2m1-17a3.5 3.5 0 0 1 0 7m2 3a6 6 0 0 1 3 5v2"/>',
 posts:'<rect x="3" y="3" width="18" height="18" rx="4"/><path d="m10 8 6 4-6 4Z"/>'
};
let channels=[],entries=new Map(),active='all',loading=false,chartRange='24h',chartScope='all',renderedScope='all',cloudHealth=null,cloudConfig={};
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
const time=t=>{const ms=typeof t==='number'?t:Date.parse(t);return Number.isFinite(ms)?new Intl.DateTimeFormat('en-GB',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',timeZone:'Europe/Vilnius'}).format(new Date(ms))+' Vilnius':'Not checked';};
const safe=u=>{try{const v=new URL(u,location.href);return v.protocol==='https:'||v.origin===location.origin?esc(v.href):'#';}catch{return '#';}};
const currentId=()=>{try{return decodeURIComponent(location.hash.match(/^#channel\/([^/]+)/)?.[1]||'');}catch{return '';}};
const currentView=()=>{const part=location.hash.split('/').at(-1).replace(/^#/,'');return ['videos','accounts'].includes(part)?part:'overview';};
const selected=()=>channels.find(c=>c.id===currentId())||null;
const videoTitle=v=>String(v.caption||v.title||'Untitled video').trim();
const valid=m=>m&&Number.isFinite(m.value);
const approx=m=>m?.approximate?'<span class="approx" aria-label="Approximately">≈</span>':'';
function total(posts,key){
 const ms=posts.map(p=>p.metrics?.[key]).filter(valid);
 return {value:ms.length?ms.reduce((s,m)=>s+m.value,0):null,count:ms.length,approximate:ms.some(m=>m.approximate),oldest:ms.map(m=>m.at).filter(Boolean).sort()[0]};
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
  out[key]={value:ms.length?ms.reduce((n,m)=>n+m.value,0):null,count:ms.reduce((n,m)=>n+(m.count||0),0),approximate:ms.some(m=>m.approximate),oldest:ms.map(m=>m.oldest).filter(Boolean).sort()[0]};
 }
 for(const key of ['postCount','accountCount','videoCount'])out[key]=list.reduce((n,s)=>n+s[key],0);
 return out;
}
function statusText(a){
 if(a.id==='youtube'&&a.status==='unavailable')return 'Content access needs verification. Last verified metrics are preserved.';
 if(a.status==='ok')return 'Public account and content list checked.';
 if(a.status==='partial')return 'Some metrics updated. Each number keeps its own observation time.';
 return 'Source unavailable. Showing the last verified metrics.';
}
function metricTitle(m){return `${m?.approximate?'Approximately ':''}${full(m?.value)} · Observed ${time(m?.at||m?.oldest)}`;}
function metricCell(m,date=true){
 if(!valid(m))return '<span class="muted">—</span>';
 return '<span class="num" tabindex="0" title="'+esc(metricTitle(m))+'">'+(m.approximate?'≈ ':'')+compact(m.value)+'</span>'+(date&&m.oldest?'<span class="tiny">'+esc(time(m.oldest))+'</span>':'');
}
function assetLink(v){return v.assetUrl?'<a class="asset-link" href="'+safe(v.assetUrl)+'" target="_blank" rel="noopener">Original video (Drive) ↗</a>':'';}
function changeFor(data,key){
 // Only compare complete, timestamped source observations; never extrapolate today's growth to 24 hours.
 const m=data?.changes24h?.[key];
 const age=Date.now()-Date.parse(m?.at);
 return valid(m)&&m.comparable===true&&age>=0&&age<3*3600000?m:null;
}
function renderStats(s,data){
 $('stats').innerHTML=[['views','Views'],['likes','Likes'],['followers','Followers'],['posts','Confirmed posts']].map(([key,label])=>{
  const m=s[key],expected=key==='followers'?s.accountCount:s.postCount,partial=key!=='posts'&&m.count<expected;
  const delta=changeFor(data,key);
  const change=key==='posts'?`${s.videoCount} tracked videos`:expected===0&&key!=='followers'?'No confirmed posts in this scope':delta?`${delta.value>0?'+':''}${compact(delta.value)} in 24h`:(data?.changes24h?.baselineAt?'24h change unavailable':'24h change · collecting history');
  const valueTitle=key==='posts'?full(m.value)+' confirmed publication links in the loaded feed':metricTitle(m);
  return '<article class="stat"><div class="stat-label"><svg viewBox="0 0 24 24" aria-hidden="true">'+ICONS[key]+'</svg>'+label+'</div><div class="stat-value" title="'+esc(valueTitle)+'" tabindex="0">'+approx(m)+compact(m.value)+'</div><p class="change '+(key==='posts'||!delta?'pending':delta.value<0?'negative':'')+'">'+esc(change)+'</p><p class="stat-meta">'+(key==='posts'?`${s.accountCount} social accounts`:key==='followers'?`${m.count} of ${expected} accounts`:`${m.count} of ${expected} publications`)+(partial?' · partial data':'')+'</p></article>';
 }).join('');
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
 $('chart-total').textContent=latest?(latest.approximate?'≈ ':'')+compact(latest.value):'—';
 $('chart-total').title=latest?full(latest.value)+' recorded views':'';
 $('chart-period').textContent=points.length?time(points[0].t)+' — '+time(latest.t):'';
 $('chart-history-start').textContent=all.length?'History since '+new Intl.DateTimeFormat('en-GB',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',timeZone:'Europe/Vilnius'}).format(new Date(all[0].t))+' · Vilnius time':'';
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
 if(!Number.isFinite(age)||age<0||age>45*60000)return {label:'Cloud job overdue',warning:true};
 if(health.status!=='completed')return {label:'Completed with errors',warning:true};
 const updated=Object.values(health.channels||{}).reduce((n,c)=>n+(c.metricsUpdated||0),0);
 return {label:updated?'Cloud job completed':'Completed · no new metrics',warning:!updated};
}
function renderCloudHealth(){
 const state=collectorStatus(cloudHealth),scope=scopedChannels();
 const records=scope.map(c=>cloudHealth?.channels?.[c.id]).filter(Boolean),count=records.reduce((n,c)=>n+(c.metricsUpdated||0),0);
 const platforms=records.flatMap(c=>Object.values(c.platforms||{})),updated=platforms.filter(p=>p.metricsUpdated>0).length;
 $('cloud-health').innerHTML='<div><span class="cloud-label">AUTONOMOUS COLLECTOR</span><strong><span class="dot '+(state.warning?'partial':'ok')+'"></span>'+esc(state.label)+'</strong><small>'+esc(time(cloudHealth?.completedAt))+'</small></div><div><span class="cloud-label">LATEST RUN</span><strong>'+full(count)+' metrics updated</strong><small>'+records.length+' of '+scope.length+' channel reports · earlier metric dates are retained</small></div><div><span class="cloud-label">PUBLIC SOURCE COVERAGE</span><strong>'+updated+' / '+platforms.length+' accounts with new metrics</strong><small>Free mode · blocked values keep their actual dates</small></div><div class="cloud-links"><a href="'+safe(cloudHealth?.runUrl||cloudConfig.runsUrl||'https://github.com/jonass-pandos/cooked-dev-stats/actions/workflows/refresh.yml')+'" target="_blank" rel="noopener">Run details ↗</a><a href="'+safe(cloudConfig.watchdogUrl||'https://github.com/jonass-pandos/cooked-dev-stats/actions/workflows/watchdog.yml')+'" target="_blank" rel="noopener">Auto-recovery ↗</a><a href="'+safe(cloudConfig.independentUrl||'https://jonass-pandos.github.io/cooked-dev-stats/')+'" target="_blank" rel="noopener">Independent site ↗</a></div>';
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
 $('workspace-switcher').innerHTML='<a class="workspace '+(!c?'active':'')+'" href="'+scopeHref(null,view)+'" '+(!c?'aria-current="page"':'')+'><span class="scope-icon" aria-hidden="true">▦</span>All channels<span class="workspace-count">'+channels.length+'</span></a>'+channels.map(x=>'<a class="workspace '+(c?.id===x.id?'active':'')+'" data-channel="'+esc(x.id)+'" href="'+scopeHref(x.id,view)+'" '+(c?.id===x.id?'aria-current="page"':'')+'><img src="'+safe(x.logo)+'" alt="">'+esc(x.name)+'</a>').join('');
 const count=scopedChannels().reduce((n,x)=>n+(entries.get(x.id)?.data?.videos.length||0),0);
 $('page-tabs').innerHTML=[['overview','Overview'],['videos','Video tracker'],['accounts','Accounts & sources']].map(([id,label])=>'<a class="page-tab '+(view===id?'active':'')+'" href="'+scopeHref(c?.id,id)+'" '+(view===id?'aria-current="page"':'')+'>'+label+(id==='videos'?'<span class="tab-count">'+count+'</span>':'')+'</a>').join('');
}
function render(){
 const c=selected(),entry=c&&entries.get(c.id),data=entry?.data,view=currentView(),scope=scopedChannels();
 renderedScope=c?.id||'all';
 renderNavigation();renderCloudHealth();
 $('channel-logo').hidden=!c;
 if(c){$('channel-logo').src=c.logo;$('channel-logo').alt=c.name;}
 $('eyebrow').textContent=c?'YOUR CHANNEL WORKSPACE':'SHARED WORKSPACE';
 $('page-title').textContent=c?c.name+'.':'All channels.';
 $('description').textContent=c?'Your stats, publications and source links. Kept together for this channel.':'Cooked Dev + Indian Builds. See the whole picture, or focus on one channel.';
 document.title=(c?c.name:'All channels')+' · '+({overview:'Overview',videos:'Video tracker',accounts:'Accounts & sources'}[view])+' · Social Stats';
 $('overview-section').hidden=view!=='overview';$('video-section').hidden=view!=='videos';$('accounts-section').hidden=view!=='accounts';
 $('channels-section').hidden=!!c;$('comparison-section').hidden=!!c;$('channel-section').hidden=!c||!data;
 $('sheet-link').href=c?.sheetUrl||'#';$('sheet-link').hidden=!c?.sheetUrl;
 $('library-link').href=c?.assetLibraryUrl||'#';$('library-link').hidden=!c?.assetLibraryUrl;
 const available=scope.filter(x=>entries.get(x.id)?.data),summaries=available.map(x=>summary(entries.get(x.id).data));
 if(available.length)renderStats(combine(summaries),data||(available.length===1?entries.get(available[0].id).data:null));
 else $('stats').innerHTML='<p class="loading">Stats are unavailable. Try reloading the feed.</p>';
 const attempts=scope.map(x=>checkedAt(entries.get(x.id)?.data)).filter(Boolean).sort();
 $('last-check').textContent=attempts.length?(c?'Feed checked: ':'Oldest feed check: ')+time(attempts[0]):'No successful feed check';
 const states=scope.map(x=>sourceState(entries.get(x.id)));
 $('refresh-dot').className='dot '+(states.some(s=>s.warning)?'partial':'ok');
 const failed=scope.filter(x=>!entries.get(x.id)?.data),fallback=scope.filter(x=>entries.get(x.id)?.fallback),problems=[];
 if(failed.length)problems.push(failed.map(x=>x.name).join(', ')+': source unavailable. Shared totals exclude these channels.');
 const catchingUp=fallback.filter(x=>entries.get(x.id)?.fallbackReason==='newer_snapshot'),unreachable=fallback.filter(x=>entries.get(x.id)?.fallbackReason!=='newer_snapshot');
 if(catchingUp.length)problems.push(catchingUp.map(x=>x.name).join(', ')+': live feed is catching up; showing a newer verified snapshot.');
 if(unreachable.length)problems.push(unreachable.map(x=>x.name).join(', ')+': live feed unavailable; showing the last saved snapshot.');
 if(scope.some(x=>{const at=checkedAt(entries.get(x.id)?.data);return at&&Date.now()-Date.parse(at)>45*60000;}))problems.push('Some source checks are over 45 minutes old. See Accounts & sources for exact times.');
 if(data?.tracking?.note)problems.push(data.tracking.note);
 $('notice').textContent=problems.join(' ');$('notice').hidden=!problems.length;
 if(view==='overview'){
  if(c&&data)renderChannel(c,data);else renderChannels();
  if(!c)renderComparison();
  renderAttention();renderViewsChart();
 }else if(view==='videos'){renderVideoFilters();renderVideos();renderResources();}
 else renderAccounts();
}
function renderChannels(){
 $('channel-count').textContent='('+channels.length+')';
 $('channels').innerHTML=channels.map(c=>{
  const entry=entries.get(c.id),d=entry?.data,s=d&&summary(d);
  return '<article class="channel" data-channel="'+esc(c.id)+'"><a class="channel-top" href="'+scopeHref(c.id)+'"><img class="channel-logo" src="'+safe(c.logo)+'" alt=""><div><h3 class="channel-name">'+esc(c.name)+'</h3><p class="channel-tagline">'+(s?s.accountCount+' platforms · '+s.postCount+' confirmed posts':'Source unavailable')+'</p></div><span class="channel-arrow" aria-hidden="true">↗</span></a><div class="channel-metrics">'+[['views','Views'],['followers','Followers'],['likes','Likes']].map(([k,label])=>'<div><strong tabindex="0" title="'+esc(metricTitle(s?.[k]))+'">'+approx(s?.[k])+compact(s?.[k]?.value)+'</strong><small>'+label+'</small></div>').join('')+'<div><strong>'+ (s?s.videoCount:'—')+'</strong><small>Videos</small></div></div><div class="channel-foot"><div>'+sourceBadge(entry)+'<span class="tiny">Feed: '+esc(time(checkedAt(d)))+'</span></div><span>'+ (d?d.accounts.map(a=>ABBR[a.id]||a.name).join(' · '):'No data')+'</span></div><div class="channel-actions"><a href="'+scopeHref(c.id,'videos')+'">Video tracker ↗</a>'+(c.assetLibraryUrl?'<a href="'+safe(c.assetLibraryUrl)+'" target="_blank" rel="noopener">Video library ↗</a>':'')+(c.sheetUrl?'<a href="'+safe(c.sheetUrl)+'" target="_blank" rel="noopener">Sheet ↗</a>':'')+'</div></article>';
 }).join('');
}
function renderComparison(){
 $('comparison-rows').innerHTML=channels.map(c=>{
  const entry=entries.get(c.id),data=entry?.data,s=data&&summary(data);
  return '<tr><td><a class="table-channel" href="'+scopeHref(c.id)+'"><img src="'+safe(c.logo)+'" alt="">'+esc(c.name)+'</a></td>'+['views','likes','followers'].map(k=>'<td class="number">'+metricCell(s?.[k],false)+'</td>').join('')+'<td class="number">'+(s?s.videoCount:'—')+'</td><td class="number">'+(s?s.postCount:'—')+'</td><td>'+sourceBadge(entry)+'<span class="tiny">'+esc(time(checkedAt(data)))+'</span></td></tr>';
 }).join('');
}
function platformSummary(data,a){return summary(data,a.id);}
function renderChannel(c,data){
 $('platforms').innerHTML=data.accounts.map(a=>{
  const s=platformSummary(data,a);
  return '<button class="platform" data-platform="'+esc(a.id)+'" aria-label="View '+esc(a.name)+' video tracking"><div class="platform-head"><span class="platform-name">'+esc(a.name)+'</span><span class="sub">'+s.postCount+' posts ↗</span></div><div class="big" title="'+esc(metricTitle(s.views))+'">'+approx(s.views)+compact(s.views.value)+'</div><div class="sub">views · '+compact(a.metrics?.followers?.value)+' followers</div><div class="status" title="'+esc(statusText(a))+'"><span class="dot '+(a.status==='ok'?'ok':'partial')+'"></span>'+(a.status==='ok'?'Checked':a.status==='partial'?'Partial metrics':'Source limited')+'</div></button>';
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
  const blocked=d.accounts.filter(a=>['unavailable','snapshot'].includes(a.status));
  if(blocked.length)issues.push({channel:c,title:'Source access needs a check',text:blocked.map(a=>a.name).join(', ')+': current collection is limited. Earlier metric values may still be visible.'});
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
 const vs=visibleVideoRows(),scope=scopedChannels(),allCount=collectVideoRows(scope,entries).length,opts=trackerOptions();
 $('video-count').textContent='('+vs.length+' of '+allCount+')';
 const channelName=channels.find(c=>c.id===opts.channel)?.name||'All channels',platformName=active==='all'?'All platforms':ABBR[active]||active;
 $('active-filter').textContent=channelName+' · '+platformName+' · '+vs.reduce((n,r)=>n+coverageFor(r,active).confirmed,0)+' confirmed posts shown';
 $('clear-filter').hidden=!opts.term&&active==='all'&&opts.coverage==='all'&&(selected()||opts.channel==='all')&&opts.sort==='views';
 $('videos').innerHTML=vs.map((r,i)=>{
  const v=r.video,count=coverageFor(r),date=Date.parse(v.publishedAt);
  return '<tr><td><div class="video-info">'+(v.thumbnail?'<img class="thumb" src="'+safe(v.thumbnail)+'" alt="" loading="lazy" onerror="this.hidden=true">':'<span class="thumb" aria-hidden="true"></span>')+'<div><button class="video-title" data-row="'+i+'">'+esc(videoTitle(v))+'</button><div class="video-meta">'+channelBadge(r.channel)+(Number.isFinite(date)?'<time datetime="'+esc(v.publishedAt)+'">'+esc(new Intl.DateTimeFormat('en-GB',{day:'2-digit',month:'short',timeZone:'Europe/Vilnius'}).format(new Date(date)))+'</time>':'')+'</div>'+assetLink(v)+'</div></div></td><td><div class="post-links">'+r.data.accounts.map(a=>{const p=v.posts[a.id];return p?.url?'<a class="post-link" href="'+safe(p.url)+'" target="_blank" rel="noopener" title="'+esc(a.name)+' · confirmed post">'+esc(ABBR[a.id]||a.name)+' ↗</a>':'<span class="post-link unconfirmed" title="'+esc(a.name)+' · publication not confirmed">'+esc(ABBR[a.id]||a.name)+' —</span>';}).join('')+'</div><p class="coverage-caption">'+count.confirmed+' / '+count.total+' platforms confirmed</p></td>'+['views','likes','comments','shares'].map(k=>'<td class="number">'+metricCell(total(postsFor(v),k))+'</td>').join('')+'</tr>';
 }).join('');
 $('videos').querySelectorAll('[data-row]').forEach(b=>b.addEventListener('click',()=>{const r=vs[Number(b.dataset.row)];detail(r.channel.id,r.video.id);}));
 $('empty').hidden=vs.length>0;
 $('empty').innerHTML=allCount?'<strong>No videos match these filters.</strong>Try another channel, platform or search.':'<strong>No tracked video publications yet.</strong>Original files are available through the channel library below. Publications appear here after they are confirmed in the source feed.';
 $('export-csv').disabled=!vs.length;
}
function renderResources(){
 $('video-resources').innerHTML=scopedChannels().map(c=>'<article class="resource-card"><h3>'+esc(c.name)+' · source files & tracking</h3>'+(c.assetLibraryUrl?'<a href="'+safe(c.assetLibraryUrl)+'" target="_blank" rel="noopener">Open video library ↗</a>':'')+(c.sheetUrl?'<a href="'+safe(c.sheetUrl)+'" target="_blank" rel="noopener">Open channel Sheet ↗</a>':'')+'<p>Original files and publication records are separate. A file in Drive is not a confirmed post.</p></article>').join('');
}
function accountHandle(a){const handle=a.expectedHandle||a.handle;return handle?(/\s/.test(handle)?handle:'@'+handle):a.expectedPageId?'Page '+a.expectedPageId:a.expectedChannelId?'Channel '+a.expectedChannelId:'Profile linked below';}
function renderAccounts(){
 $('account-groups').innerHTML=scopedChannels().map(c=>{
  const entry=entries.get(c.id),d=entry?.data;
  return '<article class="account-group"><div class="account-group-head"><img src="'+safe(c.logo)+'" alt=""><div><h3>'+esc(c.name)+'</h3><p>'+esc(time(checkedAt(d)))+' · feed check</p></div><a href="'+scopeHref(c.id)+'">Overview ↗</a></div>'+(d?d.accounts.map(a=>{
   const s=platformSummary(d,a),state=a.status==='ok'?'Checked':a.status==='partial'?'Partial metrics':'Source limited';
   return '<div class="account-row"><div class="account-row-top"><div><a class="account-name" href="'+safe(a.url)+'" target="_blank" rel="noopener">'+esc(a.name)+' ↗</a><p class="account-handle">'+esc(accountHandle(a))+'</p></div><span class="status-badge '+(a.status==='ok'?'':'warning')+'"><span class="dot '+(a.status==='ok'?'ok':'partial')+'"></span>'+state+'</span></div><div class="account-metrics"><div><strong>'+metricCell(a.metrics?.followers,false)+'</strong><small>Followers</small></div><div><strong>'+metricCell(s.views,false)+'</strong><small>Tracked views</small></div><div><strong>'+s.postCount+'</strong><small>Confirmed video posts</small></div></div><p class="account-check">Source check: '+esc(time(a.lastAttemptAt))+' · followers observed: '+esc(time(a.metrics?.followers?.at))+'</p><p class="account-note">'+esc(statusText(a))+'</p></div>';
  }).join(''):'<p class="empty">Source unavailable. No values are assumed.</p>')+(d?.tracking?.note?'<p class="account-scope-note">'+esc(d.tracking.note)+'</p>':'')+'<div class="account-resources">'+(c.assetLibraryUrl?'<a href="'+safe(c.assetLibraryUrl)+'" target="_blank" rel="noopener">Video library ↗</a>':'')+(c.sheetUrl?'<a href="'+safe(c.sheetUrl)+'" target="_blank" rel="noopener">Channel Sheet ↗</a>':'')+'<a href="'+safe(c.dataUrl)+'" target="_blank" rel="noopener">Source data ↗</a></div></article>';
 }).join('');
}
function detail(channelId,id){
 const c=channels.find(x=>x.id===channelId),data=entries.get(channelId)?.data,v=data?.videos.find(v=>v.id===id);if(!v)return;
 $('detail-channel').textContent=c.name;$('detail-title').textContent=videoTitle(v);$('detail-caption').textContent='';$('detail-caption').hidden=true;$('detail-original').innerHTML=assetLink(v);
 $('detail-rows').innerHTML=data.accounts.map(a=>{const p=v.posts[a.id];return '<tr><td>'+(p?.url?'<a href="'+safe(p.url)+'" target="_blank" rel="noopener">'+esc(a.name)+' ↗</a><span class="tiny">Confirmed publication</span>':esc(a.name)+'<span class="tiny">Publication not confirmed</span>')+'</td>'+['views','likes','comments','shares'].map(k=>'<td class="number">'+metricCell(p?.metrics?.[k],false)+'</td>').join('')+'</tr>';}).join('');
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
async function load(manual=false){
 if(loading)return;loading=true;$('reload').disabled=true;
 try{
  if(!channels.length){const r=await fetch('data/channels.json',{cache:'no-store',signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error('Channel list unavailable');const config=await r.json();if(config.version!==1||!Array.isArray(config.channels))throw Error('Invalid channels');channels=config.channels;cloudConfig=config.collector||{};}
  const healthTask=(async()=>{
   const urls=[cloudConfig.healthUrl||'https://raw.githubusercontent.com/jonass-pandos/cooked-dev-stats/main/data/health.json','data/health.json'];
   const results=await Promise.allSettled(urls.map(async url=>{const r=await fetch(url+'?v='+Date.now(),{cache:'no-store',signal:AbortSignal.timeout(8000)});if(!r.ok)throw Error('Health unavailable');return r.json();}));
   cloudHealth=newestHealth([...results.flatMap(r=>r.status==='fulfilled'?[r.value]:[]),...(cloudHealth?[cloudHealth]:[])]);
  })();
  await Promise.all(channels.map(async c=>{
   const previous=entries.get(c.id),results=await Promise.allSettled([fetchData(c.dataUrl,manual),fetchData(c.fallbackUrl,manual)]);
   const candidates=results.flatMap((r,i)=>r.status==='fulfilled'?[{data:r.value,fallback:i===1}]:[]);
   if(previous?.data)candidates.push({...previous,fallback:true});
   const chosen=newestSnapshot(candidates);
   if(chosen){chosen.fallbackReason=chosen.fallback&&results[0].status==='fulfilled'?'newer_snapshot':'unreachable';entries.set(c.id,chosen);}
   else entries.set(c.id,{data:null,fallback:true});
  }));
  await healthTask;render();
 }catch{$('notice').textContent='Could not load the channel list. Please try refreshing.';$('notice').hidden=false;}
 finally{loading=false;$('reload').disabled=false;}
}
window.addEventListener('hashchange',()=>{
 if((selected()?.id||'all')!==renderedScope){active='all';$('search').value='';$('video-channel').value='all';$('video-coverage').value='all';$('sort').value='views';}
 render();window.scrollTo({top:0,behavior:'instant'});
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
load();setInterval(load,300000);
