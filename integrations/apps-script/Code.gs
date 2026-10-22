/** Social Stats official read broker. Private project; never log or return credentials. */
const SS_CHANNELS = {
  'cooked-dev': {youtube:'UCNPkHyLJotjamsFxts47T2A',instagram:'cooked_dev',tiktok:'cooked_dev_',facebook:'61595564490107',since:'2026-10-19T00:00:00Z'},
  'indian-builds': {youtube:'UCgHxdk2zTRXwsoCrICSwiRg',instagram:'indiaanbuilds',tiktok:'indiaanbuilds',facebook:'61594164374065',since:'2026-10-20T00:00:00Z'},
  'dont-get-traced': {youtube:'UCqsTDLISgGhzA_xiQT3E9yg',instagram:'dontgettraced',tiktok:'dontgettraceed',facebook:'61595574064670',since:'2026-10-21T00:00:00Z'}
};
const SS_PLATFORMS = ['youtube','tiktok','instagram','facebook'];

function ssProp_(key) { return PropertiesService.getScriptProperties().getProperty(key); }
function ssSave_(key,value) { PropertiesService.getScriptProperties().setProperty(key,JSON.stringify(value)); }
function ssLoad_(key) { const value=ssProp_(key); return value ? JSON.parse(value) : null; }
function ssNeed_(key) { const value=ssProp_(key); if (!value) throw new Error('CONFIGURATION_REQUIRED'); return value; }
function ssInteger_(value) {
  if (typeof value==='string' && /^\d+$/.test(value)) value=Number(value);
  return Number.isSafeInteger(value) && value>=0 ? value : null;
}
function ssMetric_(metrics,key,value,field) {
  const count=ssInteger_(value);
  if(count!==null) metrics[key]={value:count,apiMetric:field};
}
function ssJSON_(value) { return ContentService.createTextOutput(JSON.stringify(value)).setMimeType(ContentService.MimeType.JSON); }
function ssHex_(bytes) { return bytes.map(x=>(x<0?x+256:x).toString(16).padStart(2,'0')).join(''); }
function ssEqual_(a,b) {
  if(typeof a!=='string'||typeof b!=='string'||a.length!==b.length) return false;
  let difference=0; for(let i=0;i<a.length;i++) difference|=a.charCodeAt(i)^b.charCodeAt(i);
  return difference===0;
}
function ssSign_(message) { return ssHex_(Utilities.computeHmacSha256Signature(message,ssNeed_('BROKER_SIGNING_KEY'),Utilities.Charset.UTF_8)); }

/** Configure secrets in Project Settings > Script properties, never in source. */
function connectionStatus() {
  const result={version:1,channels:{},webAppConfigured:!!ssProp_('WEB_APP_URL'),requestSigningConfigured:!!ssProp_('BROKER_SIGNING_KEY')};
  Object.keys(SS_CHANNELS).forEach(channel=>{
    const meta=ssLoad_('META_'+channel), tt=ssLoad_('TIKTOK_'+channel);
    result.channels[channel]={youtube:typeof YouTube!=='undefined',meta:!!meta,tiktok:!!tt};
  });
  console.log(JSON.stringify(result));
  return result;
}

function ssRequest_(event) {
  const text=(event.postData||{}).contents||'';
  if(text.length>65536) throw new Error('INVALID_REQUEST');
  const body=JSON.parse(text);
  if(typeof body.message!=='string'||!/^[a-f0-9]{64}$/.test(body.signature||'')) throw new Error('UNAUTHORIZED');
  if(!ssEqual_(ssSign_(body.message),body.signature)) throw new Error('UNAUTHORIZED');
  const parts=JSON.parse(body.message);
  if(!Array.isArray(parts)||parts.length!==7) throw new Error('INVALID_REQUEST');
  const [version,action,epoch,nonce,channel,platform,knownIds]=parts;
  if(version!==1||action!=='collect'||!Object.prototype.hasOwnProperty.call(SS_CHANNELS,channel)||!SS_PLATFORMS.includes(platform)
    ||!Number.isSafeInteger(epoch)||Math.abs(Date.now()/1000-epoch)>180||typeof nonce!=='string'||!/^[a-f0-9]{32}$/.test(nonce)
    ||!Array.isArray(knownIds)||knownIds.length>300||knownIds.some(id=>typeof id!=='string'||!/^[-A-Za-z0-9_]{1,64}$/.test(id))) throw new Error('INVALID_REQUEST');
  const lock=LockService.getScriptLock(); lock.waitLock(10000);
  try {
    const cache=CacheService.getScriptCache(), key='request_'+nonce;
    if(cache.get(key)) throw new Error('REPLAY_REJECTED');
    cache.put(key,'1',360);
  } finally { lock.releaseLock(); }
  return {channel,platform,knownIds};
}

function doPost(event) {
  try {
    const request=ssRequest_(event);
    const fn={youtube:ssYouTube_,tiktok:ssTikTok_,instagram:ssInstagram_,facebook:ssFacebook_}[request.platform];
    return ssJSON_({ok:true,observation:fn(request.channel,request.knownIds)});
  } catch(error) {
    // Do not return raw platform errors, request URLs or token-bearing payloads.
    const allowed=['CONFIGURATION_REQUIRED','UNAUTHORIZED','INVALID_REQUEST','REPLAY_REJECTED','IDENTITY_MISMATCH','RECONNECT_REQUIRED','SOURCE_UNAVAILABLE'];
    return ssJSON_({ok:false,error:allowed.includes(error.message)?error.message:'SOURCE_UNAVAILABLE'});
  }
}

function ssBase_(channel,platform,owner) {
  return {version:1,channelId:channel,platform,owner,checkedAt:new Date().toISOString(),method:'official_api',
    inventory:{complete:false,scope:'since_tracking_start',since:SS_CHANNELS[channel].since},accountMetrics:{},posts:[]};
}

function ssYouTube_(channel,knownIds) {
  const expected=SS_CHANNELS[channel].youtube;
  const owner=(YouTube.Channels.list('snippet,contentDetails,statistics',{id:expected,maxResults:1}).items||[])[0];
  if(!owner||owner.id!==expected) throw new Error('IDENTITY_MISMATCH');
  const out=ssBase_(channel,'youtube',{id:expected});
  ssMetric_(out.accountMetrics,'followers',owner.statistics.subscriberCount,'subscriberCount');
  // Subscriber counts can be rounded by YouTube; never claim exact follower counts.
  if(out.accountMetrics.followers) out.accountMetrics.followers.approximate=true;
  ssMetric_(out.accountMetrics,'publishedCount',owner.statistics.videoCount,'videoCount');
  const ids=new Set(knownIds), playlist=owner.contentDetails.relatedPlaylists.uploads;
  let pageToken;
  for(let page=0;page<10;page++) {
    const params={playlistId:playlist,maxResults:50};
    if(pageToken) params.pageToken=pageToken;
    const response=YouTube.PlaylistItems.list('snippet,contentDetails',params);
    (response.items||[]).forEach(item=>{
      const details=item.contentDetails||{}, published=details.videoPublishedAt;
      if(published&&Date.parse(published)>=Date.parse(SS_CHANNELS[channel].since)&&/^[\w-]{11}$/.test(details.videoId||'')) ids.add(details.videoId);
    });
    pageToken=response.nextPageToken;
    if(!pageToken) { out.inventory.complete=true; break; }
  }
  const all=Array.from(ids);
  for(let offset=0;offset<all.length;offset+=50) {
    const response=YouTube.Videos.list('snippet,statistics,status',{id:all.slice(offset,offset+50).join(',')});
    (response.items||[]).forEach(item=>{
      if(item.snippet.channelId!==expected||item.status.privacyStatus!=='public'||!/^[\w-]{11}$/.test(item.id)) return;
      const metrics={}, stats=item.statistics||{};
      [['views','viewCount'],['likes','likeCount'],['comments','commentCount']].forEach(([key,field])=>ssMetric_(metrics,key,stats[field],field));
      out.posts.push({id:item.id,url:'https://www.youtube.com/watch?v='+item.id,title:item.snippet.title,
        publishedAt:item.snippet.publishedAt,metrics});
    });
  }
  return out;
}

function verifyYouTubeConnection() {
  const result=Object.keys(SS_CHANNELS).map(channel=>{
    const out=ssYouTube_(channel,[]);
    return {channelId:channel,owner:out.owner,publicVideos:out.posts.length,inventoryComplete:out.inventory.complete};
  });
  console.log(JSON.stringify(result));
  return result;
}

function ssHTTP_(url,options) {
  const response=UrlFetchApp.fetch(url,Object.assign({muteHttpExceptions:true,followRedirects:false},options||{}));
  if(response.getResponseCode()!==200) throw new Error(response.getResponseCode()===401?'RECONNECT_REQUIRED':'SOURCE_UNAVAILABLE');
  const data=JSON.parse(response.getContentText());
  if(data.error && data.error.code!=='ok') throw new Error('SOURCE_UNAVAILABLE');
  return data;
}
function ssForm_(url,fields) {
  return ssHTTP_(url,{method:'post',contentType:'application/x-www-form-urlencoded',payload:fields});
}
function ssTTUser_(token) {
  return (ssHTTP_('https://open.tiktokapis.com/v2/user/info/?fields=open_id,username,follower_count,likes_count,video_count',
    {headers:{Authorization:'Bearer '+token}}).data||{}).user||{};
}
function ssTTToken_(channel) {
  const lock=LockService.getScriptLock();lock.waitLock(20000);
  try {
    let saved=ssLoad_('TIKTOK_'+channel);
    if(!saved) throw new Error('CONFIGURATION_REQUIRED');
    if(saved.expiresAt>Date.now()+600000) return saved.access_token;
    const next=ssForm_('https://open.tiktokapis.com/v2/oauth/token/',{client_key:ssNeed_('TIKTOK_CLIENT_KEY'),client_secret:ssNeed_('TIKTOK_CLIENT_SECRET'),grant_type:'refresh_token',refresh_token:saved.refresh_token});
    if(!next.access_token||!next.refresh_token||next.open_id!==saved.open_id) throw new Error('RECONNECT_REQUIRED');
    saved=Object.assign({},next,{expiresAt:Date.now()+next.expires_in*1000});
    ssSave_('TIKTOK_'+channel,saved); // Persist rotating token before any subsequent network request.
    return saved.access_token;
  } finally {lock.releaseLock();}
}
function ssTikTok_(channel,knownIds) {
  const token=ssTTToken_(channel), user=ssTTUser_(token), expected=SS_CHANNELS[channel].tiktok;
  if(user.username!==expected||!user.open_id) throw new Error('IDENTITY_MISMATCH');
  const saved=ssLoad_('TIKTOK_'+channel);
  if(saved.open_id!==user.open_id) throw new Error('IDENTITY_MISMATCH');
  const out=ssBase_(channel,'tiktok',{handle:user.username});
  [['followers','follower_count'],['profileLikes','likes_count'],['publishedCount','video_count']].forEach(([key,field])=>ssMetric_(out.accountMetrics,key,user[field],field));
  const fields='id,create_time,share_url,video_description,title,view_count,like_count,comment_count,share_count';
  const seen=new Set();let cursor;
  function accept(item) {
    const id=String(item.id), url='https://www.tiktok.com/@'+expected+'/video/'+id;
    if(!/^\d+$/.test(id)||seen.has(id)) return;
    const shared=(item.share_url||'').split('?')[0].replace(/\/$/,'');
    if(shared!==url) return;
    seen.add(id);
    const metrics={};[['views','view_count'],['likes','like_count'],['comments','comment_count'],['shares','share_count']].forEach(([key,field])=>ssMetric_(metrics,key,item[field],field));
    out.posts.push({id,url,title:item.title||item.video_description||'Untitled video',publishedAt:new Date(item.create_time*1000).toISOString(),metrics});
  }
  for(let page=0;page<10;page++) {
    const body={max_count:20};if(cursor!==undefined) body.cursor=cursor;
    const result=ssHTTP_('https://open.tiktokapis.com/v2/video/list/?fields='+fields,{method:'post',contentType:'application/json',headers:{Authorization:'Bearer '+token},payload:JSON.stringify(body)}).data;
    if(!result||!Array.isArray(result.videos)||typeof result.has_more!=='boolean') throw new Error('SOURCE_UNAVAILABLE');
    result.videos.forEach(accept);
    if(!result.has_more) {out.inventory.complete=true;break;}
    if(result.cursor===undefined||result.cursor===cursor) break;
    cursor=result.cursor;
  }
  const missing=knownIds.filter(id=>!seen.has(id));
  for(let i=0;i<missing.length;i+=20) {
    const result=ssHTTP_('https://open.tiktokapis.com/v2/video/query/?fields='+fields,{method:'post',contentType:'application/json',headers:{Authorization:'Bearer '+token},payload:JSON.stringify({filters:{video_ids:missing.slice(i,i+20)}})}).data;
    (result&&result.videos||[]).forEach(accept);
  }
  return out;
}

function ssGraph_(path,token,params) {
  const version=ssNeed_('META_GRAPH_VERSION');
  if(!/^v\d+\.0$/.test(version)||!/^[-\w]+(?:\/[-\w]+)?$/.test(path)) throw new Error('INVALID_REQUEST');
  const base='https://graph.facebook.com/'+version+'/'+path;
  if(path==='oauth/access_token') return ssForm_(base,params);
  const query=Object.entries(params||{}).map(([key,value])=>encodeURIComponent(key)+'='+encodeURIComponent(value)).join('&');
  return ssHTTP_(base+(query?'?'+query:''),{headers:{Authorization:'Bearer '+token}});
}
function ssMeta_(channel) {
  const saved=ssLoad_('META_'+channel);
  if(!saved||saved.pageId!==SS_CHANNELS[channel].facebook||!saved.pageToken) throw new Error('CONFIGURATION_REQUIRED');
  const page=ssGraph_(saved.pageId,saved.pageToken,{fields:'id,name,instagram_business_account'});
  if(page.id!==saved.pageId) throw new Error('IDENTITY_MISMATCH');
  return {saved,page};
}
function ssInstagram_(channel) {
  const {saved,page}=ssMeta_(channel), ig=(page.instagram_business_account||{}).id;
  if(!ig||ig!==saved.igId) throw new Error('IDENTITY_MISMATCH');
  const user=ssGraph_(ig,saved.pageToken,{fields:'id,username,followers_count,media_count'});
  if(user.username!==SS_CHANNELS[channel].instagram) throw new Error('IDENTITY_MISMATCH');
  const out=ssBase_(channel,'instagram',{handle:user.username});
  ssMetric_(out.accountMetrics,'followers',user.followers_count,'followers_count');
  ssMetric_(out.accountMetrics,'publishedCount',user.media_count,'media_count');
  let after;
  for(let pageIndex=0;pageIndex<10;pageIndex++) {
    const params={fields:'id,media_type,media_product_type,permalink,caption,timestamp,like_count,comments_count',limit:100};if(after) params.after=after;
    const list=ssGraph_(ig+'/media',saved.pageToken,params);
    if(!Array.isArray(list.data)) throw new Error('SOURCE_UNAVAILABLE');
    list.data.forEach(item=>{
      if(item.media_type!=='VIDEO') return;
      const match=/^https:\/\/www\.instagram\.com\/(?:reel|p)\/([\w-]+)\/?$/.exec(item.permalink||'');
      if(!match) return;
      const metrics={};ssMetric_(metrics,'likes',item.like_count,'like_count');ssMetric_(metrics,'comments',item.comments_count,'comments_count');
      ['views','shares','saved'].forEach(field=>{
        try {
          const response=ssGraph_(item.id+'/insights',saved.pageToken,{metric:field});
          const row=(response.data||[]).find(x=>x.name===field);
          const value=row&&(row.total_value?row.total_value.value:(row.values||[])[0]&&row.values[0].value);
          ssMetric_(metrics,field==='saved'?'saves':field,value,field);
        } catch(error) { /* One unsupported metric must not erase others. */ }
      });
      out.posts.push({id:match[1],url:item.permalink,title:item.caption||'Untitled video',publishedAt:item.timestamp,metrics});
    });
    after=((list.paging||{}).cursors||{}).after;
    if(!(list.paging||{}).next) {out.inventory.complete=true;break;}
    if(!after) break;
  }
  return out;
}
function ssFacebook_(channel,knownIds) {
  const {saved,page}=ssMeta_(channel), out=ssBase_(channel,'facebook',{id:page.id});
  // Video.views is retained with its API field identity; verify against the Page's UI before declaring parity.
  const fields='id,from{id},description,title,created_time,permalink_url,published,privacy,views';
  const ids=new Set(knownIds), videos=new Map();let after;
  for(let index=0;index<10;index++) {
    const params={fields,limit:100};if(after) params.after=after;
    const response=ssGraph_(page.id+'/videos',saved.pageToken,params);
    if(!Array.isArray(response.data)) throw new Error('SOURCE_UNAVAILABLE');
    response.data.forEach(item=>{videos.set(item.id,item);ids.add(item.id);});
    after=((response.paging||{}).cursors||{}).after;
    if(!(response.paging||{}).next) {out.inventory.complete=true;break;}
    if(!after) break;
  }
  ids.forEach(id=>{
    try {
      const item=videos.get(id)||ssGraph_(id,saved.pageToken,{fields});
      const privacy=(item.privacy||{}).value;
      if(String(item.id)!==id||(item.from||{}).id!==page.id||item.published!==true||privacy!=='EVERYONE') return;
      const metrics={};ssMetric_(metrics,'views',item.views,'video.views');
      out.posts.push({id,url:'https://www.facebook.com/reel/'+id,title:item.title||item.description||'Untitled video',publishedAt:item.created_time,metrics});
    } catch(error) { /* Retain known public observations if a video is no longer readable. */ }
  });
  // Reels availability in /videos and the returned view definition require a live account check.
  out.inventory.complete=false;
  return out;
}

function ssBegin_(platform,channel) {
  if(!Object.prototype.hasOwnProperty.call(SS_CHANNELS,channel)) throw new Error('INVALID_REQUEST');
  const state=Utilities.getUuid().replace(/-/g,'')+Utilities.getUuid().replace(/-/g,'');
  ssSave_('OAUTH_'+state,{platform,channel,expiresAt:Date.now()+600000});
  const redirect=ssNeed_('WEB_APP_URL');let url;
  if(platform==='tiktok') {
    url='https://www.tiktok.com/v2/auth/authorize/?'+Object.entries({client_key:ssNeed_('TIKTOK_CLIENT_KEY'),response_type:'code',scope:'user.info.basic,user.info.profile,user.info.stats,video.list',redirect_uri:redirect,state}).map(([k,v])=>k+'='+encodeURIComponent(v)).join('&');
  } else {
    const version=ssNeed_('META_GRAPH_VERSION');
    url='https://www.facebook.com/'+version+'/dialog/oauth?'+Object.entries({client_id:ssNeed_('META_APP_ID'),redirect_uri:redirect,response_type:'code',scope:'pages_show_list,pages_read_engagement,read_insights,instagram_basic,instagram_manage_insights',state}).map(([k,v])=>k+'='+encodeURIComponent(v)).join('&');
  }
  console.log(url);return url; // A short-lived authorization link, never an access token.
}
function connectTikTokCooked() { return ssBegin_('tiktok','cooked-dev'); }
function connectTikTokIndian() { return ssBegin_('tiktok','indian-builds'); }
function connectTikTokTraced() { return ssBegin_('tiktok','dont-get-traced'); }
function connectMetaCooked() { return ssBegin_('meta','cooked-dev'); }
function connectMetaIndian() { return ssBegin_('meta','indian-builds'); }
function connectMetaTraced() { return ssBegin_('meta','dont-get-traced'); }

function doGet(event) {
  const params=(event||{}).parameter||{};
  if(!params.code||!params.state||!/^[a-f0-9]{64}$/.test(params.state)) return ssJSON_({service:'Social Stats official read broker',connected:false});
  const lock=LockService.getScriptLock();lock.waitLock(20000);
  try {
    const pending=ssLoad_('OAUTH_'+params.state);
    PropertiesService.getScriptProperties().deleteProperty('OAUTH_'+params.state);
    if(!pending||pending.expiresAt<Date.now()) throw new Error('UNAUTHORIZED');
    const cfg=SS_CHANNELS[pending.channel];
    if(pending.platform==='tiktok') {
      const token=ssForm_('https://open.tiktokapis.com/v2/oauth/token/',{client_key:ssNeed_('TIKTOK_CLIENT_KEY'),client_secret:ssNeed_('TIKTOK_CLIENT_SECRET'),code:params.code,grant_type:'authorization_code',redirect_uri:ssNeed_('WEB_APP_URL')});
      if(!token.access_token||!token.refresh_token) throw new Error('RECONNECT_REQUIRED');
      const user=ssTTUser_(token.access_token);
      if(user.username!==cfg.tiktok||user.open_id!==token.open_id) throw new Error('IDENTITY_MISMATCH');
      ssSave_('TIKTOK_'+pending.channel,Object.assign({},token,{expiresAt:Date.now()+token.expires_in*1000}));
    } else {
      const token=ssGraph_('oauth/access_token','',{client_id:ssNeed_('META_APP_ID'),client_secret:ssNeed_('META_APP_SECRET'),redirect_uri:ssNeed_('WEB_APP_URL'),code:params.code});
      const long=ssGraph_('oauth/access_token','',{grant_type:'fb_exchange_token',client_id:ssNeed_('META_APP_ID'),client_secret:ssNeed_('META_APP_SECRET'),fb_exchange_token:token.access_token});
      let after,found;
      for(let index=0;index<10&&!found;index++) {
        const query={fields:'id,name,access_token,instagram_business_account',limit:100};if(after) query.after=after;
        const pages=ssGraph_('me/accounts',long.access_token,query);
        found=(pages.data||[]).find(page=>page.id===cfg.facebook);
        after=((pages.paging||{}).cursors||{}).after;
        if(!(pages.paging||{}).next||!after) break;
      }
      if(!found||!found.access_token) throw new Error('IDENTITY_MISMATCH');
      const igId=(found.instagram_business_account||{}).id;
      if(igId) {
        const ig=ssGraph_(igId,found.access_token,{fields:'id,username'});
        if(ig.username!==cfg.instagram) throw new Error('IDENTITY_MISMATCH');
      }
      ssSave_('META_'+pending.channel,{pageId:found.id,pageToken:found.access_token,igId:igId||null,connectedAt:new Date().toISOString()});
    }
    return ssJSON_({connected:true,channel:pending.channel,platform:pending.platform});
  } catch(error) { return ssJSON_({connected:false,error:'Connection not completed. Check the intended account and permissions.'}); }
  finally {lock.releaseLock();}
}
