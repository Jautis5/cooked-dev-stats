"""Public metadata fallbacks. No cookies, account tokens or media downloads."""
import datetime, json, re
import collect as base
from snapshot_merge import timestamp
import public_x


def add_post(data, platform, identity, url, caption, published=None):
    post = next((v['posts'][platform] for v in data['videos'] if str(v['posts'].get(platform, {}).get('id')) == identity), None)
    if post: return post
    if identity in data.get('tracking', {}).get('excludedPostIds', {}).get(platform, []): return None
    cutoff = timestamp(data.get('tracking', {}).get('startedAt'))
    if cutoff and (not timestamp(published) or timestamp(published) < cutoff): return None
    post = {'id': identity, 'url': url, 'metrics': {}}
    data['videos'].append({'id': platform+'-'+identity, 'number': max((v['number'] for v in data['videos']), default=0)+1,
                          'title': caption, 'caption': caption, 'publishedAt': published, 'thumbnail': None, 'assetUrl': None, 'posts': {platform: post}})
    return post


def tiktok_embed(data, account):
    handle = account.get('expectedHandle') or account['handle']
    page = base.request('https://www.tiktok.com/embed/@'+handle)
    match = re.search(r'<script[^>]+id=["\']__FRONTITY_CONNECT_STATE__["\'][^>]*>(.*?)</script>', page, re.S)
    if not match: raise ValueError('Public creator embed did not expose a video list')
    state = json.loads(match[1])
    profile = next((x for x in state.get('source', {}).get('data', {}).values() if x.get('userInfo', {}).get('uniqueId') == handle), None)
    if not profile or not isinstance(profile.get('videoList'), list): raise ValueError('Creator embed owner unverified')
    for key, field in [('followers', 'followerCount'), ('profileLikes', 'heartCount')]:
        base.setmetric(account, key, profile['userInfo'].get(field), account['url'])
    before = len(data['videos'])
    for item in profile['videoList']:
        identity = str(item.get('id', ''))
        if item.get('authorUniqueId') != handle or item.get('privateItem') is not False or not identity.isdigit(): continue
        if identity in data.get('tracking', {}).get('excludedPostIds', {}).get('tiktok', []): continue
        url = 'https://www.tiktok.com/@'+handle+'/video/'+identity
        known = any(str(v['posts'].get('tiktok', {}).get('id')) == identity for v in data['videos'])
        published = None
        if not known and data.get('tracking', {}).get('startedAt'):
            detail = base.state(base.request(url)).get('webapp.video-detail', {}).get('itemInfo', {}).get('itemStruct', {})
            if str(detail.get('id')) != identity or detail.get('author', {}).get('uniqueId') != handle: continue
            published = datetime.datetime.fromtimestamp(float(detail['createTime']), datetime.timezone.utc).isoformat()
        post = add_post(data, 'tiktok', identity, url, item.get('desc', '').split('#')[0].strip() or 'Untitled video', published)
        if post:
            base.setmetric(post, 'views', item.get('playCount'), post['url'])
    # Embeds expose a bounded recent list. They never establish a complete inventory.
    return {'status': 'partial', 'method': 'public_creator_embed', 'newVideos': len(data['videos'])-before, 'listedPosts': len(profile['videoList']), 'complete': False}


def rounded_count(text):
    match = re.fullmatch(r'([\d,.]+)\s*([KMB]?) views?', text, re.I)
    if not match: return (0, False) if text.lower() == 'no views' else (None, False)
    return round(float(match[1].replace(',', '')) * {'':1, 'K':1000, 'M':1000000, 'B':1000000000}[match[2].upper()]), bool(match[2])


def youtube_shorts(data, account):
    channel = account.get('expectedChannelId') or account['url'].rstrip('/').split('/')[-1]
    page = base.request('https://www.youtube.com/channel/'+channel+'/shorts?hl=en')
    match = re.search(r'(?:var\s+)?ytInitialData\s*=\s*', page)
    initial = json.JSONDecoder().raw_decode(page[match.end():])[0] if match else {}
    if initial.get('metadata', {}).get('channelMetadataRenderer', {}).get('externalId') != channel:
        raise ValueError('YouTube Shorts owner unverified')
    before = len(data['videos']); count = 0
    # Restrict extraction to this channel's selected Shorts tab, excluding recommendations.
    tabs = initial.get('contents', {}).get('twoColumnBrowseResultsRenderer', {}).get('tabs', [])
    selected = next((t['tabRenderer'] for t in tabs if t.get('tabRenderer', {}).get('selected')), {})
    if selected.get('title') != 'Shorts': raise ValueError('Channel did not expose its own Shorts tab')
    for node in base.walk(selected.get('content', {})):
        short = node.get('shortsLockupViewModel')
        if not short: continue
        cmd = short.get('onTap', {}).get('innertubeCommand', {})
        identity = cmd.get('reelWatchEndpoint', {}).get('videoId', '')
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}', identity): continue
        if cmd.get('commandMetadata', {}).get('webCommandMetadata', {}).get('url') != '/shorts/'+identity: continue
        meta = short.get('overlayMetadata', {})
        post = add_post(data, 'youtube', identity, 'https://www.youtube.com/shorts/'+identity, meta.get('primaryText', {}).get('content') or 'Untitled video')
        # Unknown dates cannot safely pass a legacy-content cutoff. Known posts still refresh.
        if post:
            value, approx = rounded_count(meta.get('secondaryText', {}).get('content', ''))
            # Prefer the exact feed/player observation when supplied in this run.
            prior = post.get('metrics', {}).get('views', {})
            if prior.get('at') != base.NOW or prior.get('approximate'):
                base.setmetric(post, 'views', value, post['url'], approx)
            count += 1
    return {'status': 'partial', 'method': 'public_shorts_tab', 'newVideos': len(data['videos'])-before, 'listedPosts': count, 'complete': False}


def x_public(post, account):
    handle = account.get('expectedHandle') or account['handle']
    info = json.loads(base.request('https://cdn.syndication.twimg.com/tweet-result?id='+post['id']+'&lang=en&token=0'))
    if info.get('id_str') != post['id'] or info.get('user', {}).get('screen_name', '').lower() != handle.lower():
        raise ValueError('X embedded post owner unverified')
    if not any(m.get('type') == 'video' for m in info.get('mediaDetails', [])):
        raise ValueError('X post is not an owned video')
    for key, field in [('likes', 'favorite_count'), ('comments', 'conversation_count')]:
        base.setmetric(post, key, info.get(field), post['url'])
    # The public embed has no view/repost counts. Never substitute engagement.
    return post


def refresh_fallbacks(data):
    discovery = data.setdefault('discovery', {})
    for account in data['accounts']:
        platform = account['id']
        if platform in ['tiktok', 'youtube']:
            fn = tiktok_embed if platform == 'tiktok' else youtube_shorts
            result, error = base.attempt(fn, data, account)
            prior = discovery.get(platform, {})
            discovery[platform] = dict(result or {'status':'unavailable', 'error':error, 'complete':False}, checkedAt=base.NOW,
                                       feedStatus=prior.get('status'), newVideos=(result or {}).get('newVideos', 0)+prior.get('newVideos', 0))
            if prior.get('lastCompleteAt'): discovery[platform]['lastCompleteAt'] = prior['lastCompleteAt']
        elif platform == 'x':
            result, error = base.attempt(public_x.discover, data, account, add_post)
            previous = discovery.get(platform, {})
            discovery[platform] = dict(result or {'status':'unavailable', 'error':error, 'complete':False}, checkedAt=base.NOW)
            if previous.get('lastCompleteAt'): discovery[platform]['lastCompleteAt'] = previous['lastCompleteAt']
        elif platform in ['instagram', 'facebook']:
            previous = discovery.get(platform, {})
            discovery[platform] = {'status':'session_required', 'checkedAt':base.NOW, 'complete':False,
                                   'message':'New-publication discovery requires an authorized account list; a successful metrics check is not a complete list.'}
            if previous.get('lastCompleteAt'): discovery[platform]['lastCompleteAt'] = previous['lastCompleteAt']
        if platform == 'x':
            for video in data['videos']:
                if 'x' not in video['posts']: continue
                post = video['posts']['x']
                # The timeline already supplies recent posts; query older known posts separately.
                if post.get('metrics', {}).get('views', {}).get('at') != base.NOW:
                    base.attempt(public_x.known_post, post, account)
                if not any(post.get('metrics', {}).get(k, {}).get('at') == base.NOW for k in ['likes', 'comments']):
                    base.attempt(x_public, post, account)
        fresh = any(m.get('at') == base.NOW for obj in [account]+[v['posts'][platform] for v in data['videos'] if platform in v['posts']] for m in obj.get('metrics', {}).values())
        if fresh and account.get('status') == 'unavailable':
            account.update(status='partial', lastSuccessAt=base.NOW, message='Some public metrics refreshed; publication inventory remains incomplete.')
    return data
