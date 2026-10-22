"""Import a private, DOM-visible batch into one explicitly identified public channel feed."""
import argparse, copy, datetime, json, pathlib, re
from urllib.parse import urlsplit, parse_qs
import collect_channels

def merge(data,capture):
    if capture.get('channelId')!=data.get('channelId','cooked-dev'):raise ValueError('Wrong channel')
    result=copy.deepcopy(data)
    for platform,batch in capture.get('platforms',{}).items():
        account=next((a for a in result['accounts'] if a['id']==platform),None)
        if not account or batch.get('accountUrl','').rstrip('/')!=account['url'].rstrip('/'):raise ValueError('Wrong account URL')
        if batch.get('browserProfile')!='lostastronaut.space':raise ValueError('Wrong browser profile')
        at=batch['observedAt'];observed=datetime.datetime.fromisoformat(at.replace('Z','+00:00'))
        if observed.tzinfo is None or observed.timestamp()>datetime.datetime.now(datetime.timezone.utc).timestamp()+300:raise ValueError('Invalid observation time')
        if batch.get('status')=='unavailable':
            account.update(status='unavailable',lastAttemptAt=at,message='Source unavailable; previous observations and dates preserved.')
            continue
        def metrics(target,measurements,url):
            for key,raw in measurements.items():
                raw=raw if isinstance(raw,dict) else {'value':raw}
                value=raw.get('value')
                if value is None:continue
                if isinstance(value,bool) or not isinstance(value,int) or value<0:raise ValueError('Invalid metric')
                old=target.setdefault('metrics',{}).get(key,{})
                if old.get('at') and datetime.datetime.fromisoformat(old['at'].replace('Z','+00:00'))>observed:continue
                target['metrics'][key]={'value':value,'at':at,'source':url,'method':'browser_bulk','approximate':raw.get('approximate') is True}
        metrics(account,batch.get('profileMetrics',{}),account['url'])
        active=0
        for post in batch.get('posts',[]):
            identity=str(post['id'])
            if identity in result.get('tracking',{}).get('excludedPostIds',{}).get(platform,[]):continue
            active+=1
            url=post['url'];parts=urlsplit(url)
            handle=account.get('expectedHandle') or account.get('handle')
            if parts.scheme!='https':raise ValueError('HTTPS required')
            if platform=='tiktok':
                valid=parts.hostname in ['www.tiktok.com','tiktok.com'] and parts.path==f"/@{handle}/video/{identity}"
            elif platform=='instagram':
                valid=parts.hostname in ['www.instagram.com','instagram.com'] and parts.path.rstrip('/') in [f'/reel/{identity}',f"/{handle}/reel/{identity}"]
            elif platform=='facebook':
                page_id=account.get('expectedPageId') or parse_qs(urlsplit(account['url']).query).get('id',[''])[0]
                valid=parts.hostname in ['www.facebook.com','facebook.com'] and identity.isdigit() and parts.path.rstrip('/') in [f'/reel/{identity}',f"/{page_id}/videos/{identity}"]
            elif platform=='x':
                valid=parts.hostname in ['x.com','www.x.com','twitter.com','www.twitter.com'] and identity.isdigit() and parts.path.rstrip('/').lower()==f"/{handle}/status/{identity}".lower()
            elif platform=='youtube':
                valid=bool(re.fullmatch(r'[A-Za-z0-9_-]{11}',identity)) and ((parts.hostname in ['youtube.com','www.youtube.com'] and (parts.path.rstrip('/')==f'/shorts/{identity}' or parts.path=='/watch' and parse_qs(parts.query).get('v')==[identity])) or parts.hostname=='youtu.be' and parts.path.rstrip('/')==f'/{identity}')
            else:raise ValueError('Unsupported platform')
            if not valid:raise ValueError('Wrong publication URL')
            video=next((v for v in result['videos'] if v['posts'].get(platform,{}).get('id')==identity),None)
            if video is None:
                if post.get('public') is not True or not post.get('caption'):raise ValueError('New publication needs observed Public state and caption')
                if platform=='x' and post.get('isVideo') is not True:raise ValueError('X publication must be a verified video, not a text post or repost')
                if platform=='youtube' and post.get('ownerChannelId')!=(account.get('expectedChannelId') or urlsplit(account['url']).path.rstrip('/').split('/')[-1]):raise ValueError('YouTube publication owner is not the verified channel')
                video={'id':platform+'-'+identity,'number':max((v['number'] for v in result['videos']),default=0)+1,'title':post['caption'][:110],'caption':post['caption'],'publishedAt':post.get('publishedAt'),
                    'thumbnail':None,'assetUrl':None,'posts':{platform:{'id':identity,'url':url,'metrics':{}}}}
                result['videos'].append(video)
            metrics(video['posts'][platform],post.get('metrics',{}),video['posts'][platform]['url'])
        if batch.get('completeList') is True and active==0 and not any(platform in v['posts'] for v in result['videos']):
            account['trackedEmptyConfirmedAt']=at
            metrics(account,{'trackedPublishedCount':0},account['url'])
        if batch.get('completeList') is True:
            result.setdefault('discovery',{})[platform]={'status':'checked','complete':True,'method':'browser_bulk','checkedAt':at,'lastCompleteAt':at,'listedPosts':active}
        account.update(status='partial',lastAttemptAt=at,lastSuccessAt=at,message='Visible profile and video list checked; legacy posts excluded.')
    times=[b['observedAt'] for b in capture.get('platforms',{}).values()]
    if times:result['lastAttemptAt']=result['generatedAt']=max(times)
    from publications import reconcile
    return reconcile(result)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--dashboard',required=True);args=p.parse_args()
    path=pathlib.Path(args.dashboard)
    data=merge(json.loads(path.read_text()),json.loads(pathlib.Path(args.input).read_text()))
    collect_channels.record(data,path.parent)
    print(json.dumps({'channel':data['channelId'],'videos':len(data['videos'])}))
