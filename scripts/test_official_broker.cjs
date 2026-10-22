const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const source = fs.readFileSync(require('node:path').join(__dirname, '../integrations/apps-script/Code.gs'), 'utf8');

function runtime(values={}) {
  const properties=new Map(Object.entries(values));
  const cache=new Map();
  const logs=[];
  const context=vm.createContext({console:{log:value=>logs.push(value)},
    PropertiesService:{getScriptProperties:()=>({getProperty:key=>properties.get(key)||null,setProperty:(key,value)=>properties.set(key,value),deleteProperty:key=>properties.delete(key)})},
    LockService:{getScriptLock:()=>({waitLock:()=>{},releaseLock:()=>{}})},
    CacheService:{getScriptCache:()=>({get:key=>cache.get(key),put:(key,value)=>cache.set(key,value)})},
    Utilities:{Charset:{UTF_8:'utf8'},computeHmacSha256Signature:(message,key)=>Array.from(crypto.createHmac('sha256',key).update(message).digest()),getUuid:()=>crypto.randomUUID()},
    ContentService:{MimeType:{JSON:'json'},createTextOutput:text=>({text,setMimeType(){return this;}})}
  });
  vm.runInContext(source,context);
  return {context,properties,logs};
}

{
  const {context}=runtime({BROKER_SIGNING_KEY:'test-only-signing-key-32-characters-long'});
  const message=JSON.stringify([1,'collect',Math.floor(Date.now()/1000),'a'.repeat(32),'cooked-dev','youtube',[]]);
  const signature=crypto.createHmac('sha256','test-only-signing-key-32-characters-long').update(message).digest('hex');
  const event={postData:{contents:JSON.stringify({message,signature})}};
  assert.equal(context.ssRequest_(event).channel,'cooked-dev');
  assert.throws(()=>context.ssRequest_(event),/REPLAY_REJECTED/);
  const altered=message.replace('youtube','facebook');
  assert.throws(()=>context.ssRequest_({postData:{contents:JSON.stringify({message:altered,signature})}}),/UNAUTHORIZED/);
  assert.equal(JSON.parse(context.doGet({}).text).connected,false);
}

{
  const {context}=runtime();
  context.YouTube={Channels:{list:()=>({items:[{id:'UCgHxdk2zTRXwsoCrICSwiRg',statistics:{subscriberCount:'0',videoCount:'1'},contentDetails:{relatedPlaylists:{uploads:'uploads'}}}]})},
    PlaylistItems:{list:()=>({items:[{contentDetails:{videoId:'abcdefghijk',videoPublishedAt:'2026-10-21T12:00:00Z'}}]})},
    Videos:{list:()=>({items:[
      {id:'abcdefghijk',snippet:{channelId:'UCgHxdk2zTRXwsoCrICSwiRg',title:'Public',publishedAt:'2026-10-21T12:00:00Z'},status:{privacyStatus:'public'},statistics:{viewCount:'0',likeCount:'1'}},
      {id:'private____',snippet:{channelId:'UCgHxdk2zTRXwsoCrICSwiRg',title:'Private'},status:{privacyStatus:'private'},statistics:{viewCount:'999'}},
      {id:'wrong______',snippet:{channelId:'wrong'},status:{privacyStatus:'public'},statistics:{viewCount:'999'}}]})}};
  const out=context.ssYouTube_('indian-builds',[]);
  assert.equal(out.posts.length,1);
  assert.equal(out.posts[0].metrics.views.value,0);
  assert.equal(out.inventory.complete,true);
  assert.equal(out.accountMetrics.followers.approximate,true);
  assert.throws(()=>context.ssYouTube_('cooked-dev',[]),/IDENTITY_MISMATCH/);
}

{
  const {context}=runtime();
  context.YouTube={Channels:{list:()=>({items:[{id:'UCqsTDLISgGhzA_xiQT3E9yg',statistics:{videoCount:'0'}}]})},
    PlaylistItems:{list:()=>{throw new Error('Empty channel has no uploads playlist');}}};
  const out=context.ssYouTube_('dont-get-traced',[]);
  assert.equal(out.inventory.complete,true);
  assert.equal(out.posts.length,0);
}

{
  const saved={access_token:'expired',refresh_token:'old-refresh',open_id:'owner',expiresAt:0};
  const {context,properties,logs}=runtime({TIKTOK_CLIENT_KEY:'test-key',TIKTOK_CLIENT_SECRET:'test-secret','TIKTOK_indian-builds':JSON.stringify(saved)});
  const fetched=[];
  context.UrlFetchApp={fetch:(url,options)=>{
    fetched.push({url,options});
    let result;
    if(url.includes('/oauth/token/')) result={access_token:'next-access',refresh_token:'next-refresh',open_id:'owner',expires_in:86400};
    else if(url.includes('/user/info/')) {
      assert.equal(JSON.parse(properties.get('TIKTOK_indian-builds')).refresh_token,'next-refresh');
      result={data:{user:{open_id:'owner',username:'indian_builds',follower_count:0}},error:{code:'ok'}};
    } else result={data:{videos:[{id:'123',share_url:'https://www.tiktok.com/@indian_builds/video/123',create_time:1792594934,view_count:0,like_count:2}],has_more:false},error:{code:'ok'}};
    return {getResponseCode:()=>200,getContentText:()=>JSON.stringify(result)};
  }};
  const out=context.ssTikTok_('indian-builds',[]);
  assert.equal(out.posts[0].metrics.views.value,0);
  assert.equal(out.inventory.complete,true);
  assert.equal(JSON.parse(properties.get('TIKTOK_indian-builds')).refresh_token,'next-refresh');
  assert.ok(!JSON.stringify(out).includes('next-access'));
  assert.ok(!JSON.stringify(out).includes('next-refresh'));
  assert.deepEqual(logs,[]);
}

{
  const {context}=runtime();
  const metrics={};
  for(const value of [null,undefined,true,-1,'1K',1.5]) context.ssMetric_(metrics,'views',value,'view_count');
  assert.deepEqual(metrics,{});
  context.ssMetric_(metrics,'views','0','view_count');
  assert.equal(metrics.views.value,0);
}

const manifest=JSON.parse(fs.readFileSync(require('node:path').join(__dirname,'../integrations/apps-script/appsscript.json'),'utf8'));
{
  const {context}=runtime({BROKER_SIGNING_KEY:'test-only-signing-key-32-characters-long'});
  const cursor=context.ssCursor_('cooked-dev','instagram','123','replies','','456');
  assert.equal(context.ssReadCursor_(cursor,'cooked-dev','instagram','123').parentId,'456');
  assert.throws(()=>context.ssReadCursor_(cursor,'indian-builds','instagram','123'),/INVALID_REQUEST/);
  assert.throws(()=>context.ssReadCursor_(cursor,'cooked-dev','instagram','999'),/INVALID_REQUEST/);
  assert.throws(()=>context.ssReadCursor_(cursor.replace('456','777'),'cooked-dev','instagram','123'),/INVALID_REQUEST/);
  assert.equal(context.ssCapabilities_('cooked-dev','instagram').identityVerified,false);
  assert.equal(context.ssCapabilities_('cooked-dev','tiktok').status,'business_access_required');
  assert.throws(()=>context.ssTTBusiness_('cooked-dev'),/BUSINESS_ACCESS_REQUIRED/);
}
{
  const {context}=runtime({BROKER_SIGNING_KEY:'test-only-signing-key-32-characters-long'});
  context.ssIGIdentity_=()=>({id:'owned',token:'not-returned'});
  context.ssIGList_=()=>({data:[{id:'123',permalink:'https://www.instagram.com/reel/OWNED/'}]});
  const requested=[];
  context.ssGraph_=(path,token,params)=>{
    requested.push(path);
    return {data:[{id:'456',text:'Real comment',username:'viewer',timestamp:'2026-10-22T08:00:00Z',like_count:0},{id:'456',text:'Duplicate',timestamp:'2026-10-22T08:00:00Z'}]};
  };
  const first=context.ssComments_('cooked-dev','instagram',{postId:'OWNED'});
  assert.equal(first.comments.length,1);
  assert.equal(first.comments[0].likes,0);
  assert.equal(first.pageComplete,true);
  assert.equal(first.allThreadsComplete,false);
  assert.ok(first.comments[0].replyCursor);
  context.ssComments_('cooked-dev','instagram',{postId:'OWNED',cursor:first.comments[0].replyCursor});
  assert.equal(requested[1],'456/replies');
  assert.throws(()=>context.ssComments_('cooked-dev','instagram',{postId:'FOREIGN'}),/POST_NOT_FOUND/);
  assert.ok(!JSON.stringify(first).includes('not-returned'));
}
{
  const {context}=runtime({BROKER_SIGNING_KEY:'test-only-signing-key-32-characters-long'});
  context.ssTTBusiness_=()=>({access_token:'not-a-display-token',open_id:'private',handle:'cooked_dev_'});
  context.ssTTBusinessPost_=()=>({item_id:'123',share_url:'https://www.tiktok.com/@cooked_dev_/video/123'});
  let requested;
  context.ssTTBusinessGet_=(saved,path,params)=>{
    requested={path,params};
    return {comments:[{comment_id:'9007199254740993123',video_id:'123',text:'Keep ID precision',create_time:'1792656000',likes:0,replies:4,status:'PUBLIC'}],cursor:30,has_more:true};
  };
  const first=context.ssComments_('cooked-dev','tiktok',{postId:'123'});
  assert.equal(first.comments[0].id,'9007199254740993123');
  assert.equal(first.comments[0].likes,0);
  assert.equal(first.pageComplete,false);
  assert.equal(requested.params.include_replies,false);
  assert.ok(first.comments[0].replyCursor);
  context.ssTTBusinessGet_=()=>({comments:[],cursor:30,has_more:true});
  assert.throws(()=>context.ssComments_('cooked-dev','tiktok',{postId:'123',cursor:first.nextCursor}),/SOURCE_UNAVAILABLE/);
}
{
  const {context}=runtime();
  context.ssTTBusiness_=()=>({});
  context.ssTTBusinessPost_=()=>({share_url:'https://www.tiktok.com/@cooked_dev_/video/123',video_views:0,reach:7,average_time_watched:2.5,impression_sources:[{impression_source:'Search',percentage:0.5}]});
  const result=context.ssTraffic_('cooked-dev','tiktok',{postId:'123'});
  assert.equal(result.metrics.video_views.value,0);
  assert.equal(result.metrics.average_time_watched.value,2.5);
  assert.ok(result.unavailable.includes('website_clicks'));
  assert.equal(result.metrics.website_clicks,undefined);
}
assert.deepEqual(manifest.oauthScopes.sort(),['https://www.googleapis.com/auth/script.external_request','https://www.googleapis.com/auth/youtube.readonly']);
console.log('PASS: HMAC/replay, owner checks, empty channels, token rotation, private cursors/replies, deduplication, zero/null, traffic precision and unchanged Google scopes.');
