"""Refresh additional registered channels, keeping each channel's feed separate."""
import datetime, json, pathlib, re, sys
from urllib.parse import urlsplit
import collect as base

ROOT=pathlib.Path(__file__).resolve().parents[1]

def youtube_profile(account,page):
    marker=re.search(r'(?:var\s+)?ytInitialData\s*=\s*',page)
    initial=json.JSONDecoder().raw_decode(page[marker.end():])[0] if marker else {}
    if initial.get('metadata',{}).get('channelMetadataRenderer',{}).get('externalId')!=account['expectedChannelId']:
        raise ValueError('YouTube channel identity unverified')
    texts=[node[k] for node in base.walk(initial) for k in ['simpleText','text','content'] if isinstance(node.get(k),str)]
    for text in texts:
        match=re.fullmatch(r'([\d,.]+)([KMB]?) subscribers?',text,re.I)
        if match:
            value=float(match[1].replace(',',''))*{'':1,'K':1000,'M':1000000,'B':1000000000}[match[2].upper()]
            base.setmetric(account,'followers',round(value),account['url'],bool(match[2]));break
    empty=any("channel doesn't have any content" in t.lower() or 'channel doesn’t have any content' in t.lower() or 'channel has no content' in t.lower() for t in texts)
    if empty:
        base.setmetric(account,'publishedCount',0,account['url']);base.setmetric(account,'trackedPublishedCount',0,account['url'])
        account['trackedEmptyConfirmedAt']=base.NOW
    if empty or any(m.get('at')==base.NOW for m in account.get('metrics',{}).values()):
        account.update(status='partial',lastSuccessAt=base.NOW,message='Verified YouTube profile checked; metric observation dates retained.')
    return account

def youtube_video(post,channel_id):
    return base.youtube_video(post,channel_id)

def tracked_item(data, item, handle):
    author=item.get('author',{})
    author=author.get('uniqueId') if isinstance(author,dict) else author
    if author!=handle or not str(item.get('id','')).isdigit():return False
    if str(item['id']) in data.get('tracking',{}).get('excludedPostIds',{}).get('tiktok',[]):return False
    start=data.get('tracking',{}).get('startedAt')
    if start:
        try:
            created=float(item['createTime'])
            if created<datetime.datetime.fromisoformat(start.replace('Z','+00:00')).timestamp():return False
        except (KeyError,ValueError,TypeError):return False
    return True

def refresh(data):
    now=base.NOW
    data['lastAttemptAt']=now
    from discover_public import discover_youtube
    yt=next((a for a in data['accounts'] if a['id']=='youtube'),None)
    if yt:
        added,error=base.attempt(discover_youtube,data,yt,base.request,base.setmetric)
        data.setdefault('discovery',{})['youtube']={'checkedAt':now,'status':'unavailable' if error else 'checked','newVideos':added or 0}
    for account in data['accounts']:
        account.update(lastAttemptAt=now,status='unavailable',message='Public source unavailable; previous observations preserved.')
        platform=account['id']
        if platform=='tiktok':
            scope,error=base.attempt(lambda:base.state(base.request(account['url'])).get('webapp.user-detail',{}))
            info=(scope or {}).get('userInfo',{})
            expected=account['expectedHandle']
            if info.get('user',{}).get('uniqueId')==expected:
                stats=info.get('statsV2') or info.get('stats') or {}
                base.setmetric(account,'followers',stats.get('followerCount'),account['url'])
                # Account-wide likes include legacy content and never enter tracked-video likes.
                base.setmetric(account,'profileLikes',stats.get('heartCount'),account['url'])
                account.update(status='partial',lastSuccessAt=now,message='Profile checked; tracked content excludes legacy posts.')
                for item in (scope or {}).get('itemList',[]):
                    if not isinstance(item,dict) or not tracked_item(data,item,expected):continue
                    if any(v['posts'].get('tiktok',{}).get('id')==str(item['id']) for v in data['videos']):continue
                    caption=item.get('desc','').split('#')[0].strip()
                    data['videos'].append({'id':'tt-'+str(item['id']),'number':max((v['number'] for v in data['videos']),default=0)+1,
                        'title':caption[:110] or 'Untitled video','caption':caption,'publishedAt':datetime.datetime.fromtimestamp(float(item['createTime']),datetime.timezone.utc).isoformat(),
                        'thumbnail':None,'assetUrl':None,'posts':{'tiktok':{'id':str(item['id']),'url':account['url']+'/video/'+str(item['id']),'metrics':{}}}})
        elif platform=='youtube':
            page,error=base.attempt(base.request,account['url']+'?hl=en')
            if page:base.attempt(youtube_profile,account,page)
        elif platform in ['facebook','x']:
            # These sources may serve a login wall: reachability never verifies metrics.
            base.attempt(base.request,account['url'])
            account['message']=account['name']+' list metrics need the connected Lost Chrome session; previous observations preserved.'
        refreshed=0
        for video in data['videos']:
            post=video['posts'].get(platform)
            if not post:continue
            fn={'tiktok':base.tiktok_video,'instagram':base.instagram_video}.get(platform)
            if platform=='youtube':fn=lambda post:youtube_video(post,account['expectedChannelId'])
            if fn is None:continue
            result,error=base.attempt(fn,post)
            if result:
                video['posts'][platform]=result;refreshed+=1
        fresh=any(m.get('at')==now for v in data['videos'] for m in v['posts'].get(platform,{}).get('metrics',{}).values())
        if refreshed or fresh:account.update(status='partial',lastSuccessAt=now,message='Public video metrics updated; per-metric dates retained.')
    data['generatedAt']=now
    data['cloudCollection']={'at':now,'method':'public_cloud','metricsUpdated':{a['id']:sum(m.get('at')==now for v in data['videos'] for m in v['posts'].get(a['id'],{}).get('metrics',{}).values())+sum(m.get('at')==now for m in a.get('metrics',{}).values()) for a in data['accounts']}}
    return data

def record(data,directory):
    now=data['lastAttemptAt']
    posts=[p for v in data['videos'] for p in v['posts'].values()]
    ms=[p.get('metrics',{}).get('views') for p in posts]
    measured=[m for m in ms if m and isinstance(m.get('value'),int)]
    empty=not posts and all(a.get('trackedEmptyConfirmedAt') and a.get('metrics',{}).get('trackedPublishedCount',{}).get('value')==0 for a in data['accounts'])
    if measured or empty:
        data['history']=(data.get('history',[])+[{'at':now,'views':sum(m['value'] for m in measured),'posts':len(posts),'approximate':any(m.get('approximate') for m in measured),'partial':len(measured)<len(posts)}])[-2160:]
    base.update_changes(data,directory=directory);base.exports(data,directory=directory);base.archive(data,directory=directory)
    (pathlib.Path(directory)/'latest.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':
    registry=json.loads((ROOT/'data/channels.json').read_text())
    for channel in registry['channels']:
        if channel['id']=='cooked-dev':continue
        path=(ROOT/channel['dataPath']).resolve()
        if not path.is_relative_to(ROOT/'data'):raise ValueError('Channel data must stay in data/')
        data=json.loads(path.read_text())
        if data.get('channelId')!=channel['id']:raise ValueError('Channel identity mismatch')
        if '--export-only' not in sys.argv:data=refresh(data)
        record(data,path.parent)
        print(json.dumps({'channel':channel['id'],'videos':len(data['videos']),'platforms':{a['id']:a['status'] for a in data['accounts']}}))
