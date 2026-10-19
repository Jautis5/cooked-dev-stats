"""Refresh public, account-matched metrics. A failed request never overwrites a value with zero."""
import concurrent.futures, csv, datetime, html, io, json, os, pathlib, re, sys, time, urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36'
def request(url):
 req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept-Language':'en-US,en;q=0.9'})
 with urllib.request.urlopen(req,timeout=25) as r:
  if r.status!=200:raise ValueError('HTTP '+str(r.status))
  return r.read(5_000_000).decode('utf8','replace')
def walk(x):
 if isinstance(x,dict):
  yield x
  for v in x.values():yield from walk(v)
 elif isinstance(x,list):
  for v in x:yield from walk(v)
def num(v):
 if isinstance(v,bool) or v is None:return None
 try:
  n=int(v)
  return n if n>=0 else None
 except (ValueError,TypeError):return None
def setmetric(obj,key,value,url,approx=False):
 value=num(value)
 if value is not None:obj.setdefault('metrics',{})[key]={'value':value,'at':NOW,'source':url,'approximate':approx}
def state(text):
 m=re.search(r'<script[^>]+id=["\']__UNIVERSAL_DATA_FOR_REHYDRATION__["\'][^>]*>(.*?)</script>',text,re.S)
 if not m:raise ValueError('Viešas statistikos blokas nepasiekiamas')
 return json.loads(m.group(1)).get('__DEFAULT_SCOPE__',{})
def tiktok_video(post):
 s=state(request(post['url'])).get('webapp.video-detail',{})
 v=s.get('itemInfo',{}).get('itemStruct',{})
 if str(v.get('id'))!=str(post['id']):raise ValueError('Įrašo tapatybė nepatvirtinta')
 stats=v.get('statsV2') or v.get('stats') or {}
 if not stats:raise ValueError('Statistikos nėra')
 for key,field in [('views','playCount'),('likes','diggCount'),('comments','commentCount'),('shares','shareCount'),('saves','collectCount')]:setmetric(post,key,stats.get(field),post['url'])
 return post
def instagram_video(post):
 import yt_dlp
 with yt_dlp.YoutubeDL({'quiet':True,'no_warnings':True,'skip_download':True,'socket_timeout':20,'retries':0,'extractor_retries':0,'ignore_no_formats_error':True}) as ydl:
  info=ydl.extract_info(post['url'],download=False)
 if str(info.get('id'))!=post['id']:raise ValueError('Įrašo tapatybė nepatvirtinta')
 for key,field in [('views','view_count'),('likes','like_count'),('comments','comment_count'),('shares','repost_count')]:setmetric(post,key,info.get(field),post['url'])
 if not any(m.get('at')==NOW for m in post['metrics'].values()):raise ValueError('Statistikos nėra')
 return post
def attempt(func,*args):
 try:return func(*args),None
 except Exception as e:return None,str(e)[:180]
def exports(data):
 def dump(name,rows):
  with (ROOT/f'data/{name}.csv').open('w',newline='',encoding='utf8') as f:
   csv.writer(f).writerows(rows)
 rows=[['Video Nr.','Video','Platforma','Nuoroda','Peržiūros','Patiktukai','Komentarai','Pasidalinimai','Peržiūrų patikra','Statistikos patikra','Būsena']]
 for v in data['videos']:
  for account in data['accounts']:
   p=v['posts'].get(account['id'])
   if not p:continue
   m=p.get('metrics',{});values=[m.get(k,{}).get('value','') for k in ['views','likes','comments','shares']]
   rows.append([v['number'],v['title'],account['name'],p['url'],*values,m.get('views',{}).get('at',''),max((x.get('at','') for x in m.values()),default=''),account['status']])
 dump('posts',rows)
 platforms=[['Platforma','Sekėjai','Rasti video','Peržiūros','Patiktukai','Komentarai','Pasidalinimai','Sekėjų patikra','Paskutinis bandymas','Būsena']]
 for a in data['accounts']:
  posts=[v['posts'][a['id']] for v in data['videos'] if a['id'] in v['posts']]
  totals=[]
  for k in ['views','likes','comments','shares']:
   vals=[p['metrics'][k]['value'] for p in posts if k in p.get('metrics',{})]
   totals.append(sum(vals) if vals else (0 if a.get('emptyConfirmedAt') and a['status']=='ok' else ''))
  platforms.append([a['name'],a.get('metrics',{}).get('followers',{}).get('value',''),len(posts),*totals,a.get('metrics',{}).get('followers',{}).get('at',''),a.get('lastAttemptAt',''),a['status']])
 dump('platforms',platforms)
def archive(data):
 # Preserve public observations beyond the compact history window. No token or private report is archived.
 stamp=data.get('lastAttemptAt') or NOW
 folder=ROOT/'data/archive';folder.mkdir(parents=True,exist_ok=True)
 path=folder/(stamp[:7]+'.jsonl')
 observation={'attemptAt':stamp,
  'accounts':[{k:a.get(k) for k in ['id','url','metrics','status','lastAttemptAt','lastSuccessAt']} for a in data['accounts']],
  'videos':[{'id':v['id'],'number':v['number'],'assetUrl':v.get('assetUrl'),
   'posts':{p:{k:post.get(k) for k in ['id','url','metrics']} for p,post in v['posts'].items()}} for v in data['videos']]}
 if path.exists():
  lines=path.read_text(encoding='utf8').splitlines()
  if lines and json.loads(lines[-1]).get('attemptAt')==stamp:return
 with path.open('a',encoding='utf8') as f:f.write(json.dumps(observation,ensure_ascii=False,separators=(',',':'))+'\n')
def collect(data):
 data['lastAttemptAt']=NOW
 accounts={a['id']:a for a in data['accounts']}
 for a in accounts.values():a.update(lastAttemptAt=NOW,status='unavailable',message='Viešas šaltinis nepateikė patikimos statistikos.')
 tt=accounts['tiktok']
 profile,error=attempt(lambda:state(request(tt['url'])).get('webapp.user-detail',{}).get('userInfo',{}))
 if profile and profile.get('user',{}).get('uniqueId')=='cooked_dev_':
  st=profile.get('statsV2') or profile.get('stats') or {}
  setmetric(tt,'followers',st.get('followerCount'),tt['url']);setmetric(tt,'profileLikes',st.get('heartCount'),tt['url']);setmetric(tt,'publishedCount',st.get('videoCount'),tt['url'])
  tt.update(status='partial',lastSuccessAt=NOW,message='Profilio skaičiai atnaujinti.')
  # New posts are adopted only when the actual public profile supplies their IDs and author.
  for item in profile.get('itemList',[]):
   if not isinstance(item,dict) or not item.get('id'):continue
   author=item.get('author',{});handle=author.get('uniqueId') if isinstance(author,dict) else author
   if handle!='cooked_dev_':continue
   if any(v['posts'].get('tiktok',{}).get('id')==str(item['id']) for v in data['videos']):continue
   caption=item.get('desc','').split('#')[0].strip()
   def normalize(t):return re.sub(r'[^a-z0-9]','',t.lower())
   existing=next((v for v in data['videos'] if normalize(v['caption'])==normalize(caption)),None)
   if not existing:
    existing={'id':'tt-'+str(item['id']),'number':max(v['number'] for v in data['videos'])+1,'title':caption[:110],'caption':caption,'publishedAt':datetime.datetime.fromtimestamp(int(item.get('createTime',0)),datetime.timezone.utc).isoformat(),'thumbnail':None,'assetUrl':None,'posts':{}}
    data['videos'].append(existing)
   existing['posts']['tiktok']={'id':str(item['id']),'url':tt['url']+'/video/'+str(item['id']),'metrics':{}}
 elif error:tt['message']='TikTok profilis: '+error
 jobs=[];results={'tiktok':[],'instagram':[]}
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  for v in data['videos']:
   for platform,func in [('tiktok',tiktok_video),('instagram',instagram_video)]:
    if platform in v['posts']:jobs.append((platform,v,pool.submit(attempt,func,v['posts'][platform])))
  for platform,v,f in jobs:
   post,error=f.result();results[platform].append(not error)
   if post:v['posts'][platform]=post
   elif error:print(platform,v['id'],'unavailable',file=sys.stderr)
 for platform,oks in results.items():
  a=accounts[platform];count=sum(oks)
  if count:
   fresh_views=all(v['posts'][platform].get('metrics',{}).get('views',{}).get('at')==NOW for v in data['videos'] if platform in v['posts'])
   a.update(status='ok' if count==len(oks) and fresh_views else 'partial',lastSuccessAt=NOW,message=f'Atnaujinta {count}/{len(oks)} įrašų. Atskirų rodiklių patikros laikas gali skirtis.')
 # YouTube public page: only explicit public empty-state text justifies zero uploads.
 yt=accounts['youtube'];page,error=attempt(request,yt['url']+'?hl=en')
 if page:
  try:
   marker=re.search(r'(?:var\s+)?ytInitialData\s*=\s*',page)
   initial=json.JSONDecoder().raw_decode(page[marker.end():])[0] if marker else {}
   texts=[]
   for node in walk(initial):
    for key in ['simpleText','text','content']:
     if isinstance(node.get(key),str):texts.append(node[key])
   for t in texts:
    m=re.fullmatch(r'([\d,.]+)([KMB]?) subscribers?',t,re.I)
    if m:
     n=float(m[1].replace(',',''))*({'K':1000,'M':1000000,'B':1000000000}.get(m[2].upper(),1));setmetric(yt,'followers',round(n),yt['url'],bool(m[2]));break
   empty=any('channel doesn’t have any content' in t.lower() or "channel doesn't have any content" in t.lower() or 'channel has no content' in t.lower() for t in texts)
   if empty:yt.update(status='ok',lastSuccessAt=NOW,emptyConfirmedAt=NOW,message='Viešame kanale turinio nėra.')
   elif any(m.get('at')==NOW for m in yt['metrics'].values()):yt.update(status='partial',lastSuccessAt=NOW,message='Profilis pasiekiamas. Visas publikacijų sąrašas nepatvirtintas.')
  except Exception:pass
 # X and Facebook can require account APIs. A login wall or challenge is never parsed as zero.
 for platform in ['x','facebook']:
  a=accounts[platform];page,error=attempt(request,a['url'])
  if page and platform=='x' and '@Cooked_Deev' in html.unescape(page) and re.search(r'@Cooked_Deev (?:hasn.t posted|has no posts)',html.unescape(page),re.I):
   a.update(status='ok',lastSuccessAt=NOW,emptyConfirmedAt=NOW,message='Viešas profilis patvirtina, kad įrašų nėra.')
  else:a['message']='Automatinė vieša statistika nepasiekiama. Palikti paskutiniai patikrinti duomenys.'
 data['generatedAt']=NOW
 total=sum(m['value'] for v in data['videos'] for p in v['posts'].values() for k,m in p['metrics'].items() if k=='views')
 sample={'at':NOW,'views':total,'posts':sum(len(v['posts']) for v in data['videos']),'updatedPlatforms':[a['id'] for a in accounts.values() if a.get('lastSuccessAt')==NOW]}
 data['history']=(data.get('history',[])+[sample])[-2160:]
 return data
if __name__=='__main__':
 path=ROOT/'data/latest.json';data=json.loads(path.read_text())
 if '--export-only' not in sys.argv:data=collect(data)
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');exports(data)
 if '--export-only' not in sys.argv:archive(data)
 print(json.dumps({'videos':len(data['videos']),'attemptAt':data['lastAttemptAt'],'platforms':{a['id']:a['status'] for a in data['accounts']}}))
