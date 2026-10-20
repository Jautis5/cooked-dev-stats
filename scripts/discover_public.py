"""Read owner-verified YouTube public feeds without a login, key or video download."""
import re, xml.etree.ElementTree as ET
from urllib.parse import parse_qs, urlsplit
from snapshot_merge import timestamp
NS = {'atom': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015', 'media': 'http://search.yahoo.com/mrss/'}


def discover_youtube(data, account, request, observe=None):
    channel = account.get('expectedChannelId') or urlsplit(account['url']).path.rsplit('/', 1)[-1]
    if not re.fullmatch(r'UC[A-Za-z0-9_-]{22}', channel):
        raise ValueError('Unverified channel identity')
    feed_url = 'https://www.youtube.com/feeds/videos.xml?channel_id=' + channel
    root = ET.fromstring(request(feed_url))
    owner = root.findtext('yt:channelId', namespaces=NS)
    links = [link.get('href') for link in root.findall('atom:link', NS) if link.get('rel') == 'alternate']
    # YouTube's root feed ID omits UC; its alternate URL and each video retain the full ID.
    if owner not in [channel, channel[2:]] or 'https://www.youtube.com/channel/' + channel not in links:
        raise ValueError('Wrong public feed owner')
    known = {str(v['posts']['youtube']['id']): v['posts']['youtube'] for v in data['videos'] if 'youtube' in v['posts']}
    excluded = set(data.get('tracking', {}).get('excludedPostIds', {}).get('youtube', []))
    cutoff = timestamp(data.get('tracking', {}).get('startedAt')) or min((timestamp(v.get('publishedAt')) for v in data['videos'] if timestamp(v.get('publishedAt'))), default=0)
    added = 0
    for entry in root.findall('atom:entry', NS):
        video_id = entry.findtext('yt:videoId', namespaces=NS)
        if not video_id or not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id) or video_id in excluded:
            continue
        if entry.findtext('yt:channelId', namespaces=NS) != channel:
            continue
        link = next((node.get('href') for node in entry.findall('atom:link', NS) if node.get('rel') == 'alternate'), None)
        url = urlsplit(link or '')
        if url.scheme != 'https' or url.hostname not in ['www.youtube.com', 'youtube.com'] or parse_qs(url.query).get('v') != [video_id]:
            continue
        post = known.get(video_id)
        if post is None:
            published = entry.findtext('atom:published', namespaces=NS)
            if not timestamp(published) or not cutoff or timestamp(published) < cutoff:
                continue
            caption = entry.findtext('atom:title', namespaces=NS) or 'Untitled video'
            post = {'id': video_id, 'url': link, 'metrics': {}}
            data['videos'].append({'id': 'yt-' + video_id, 'number': max((v['number'] for v in data['videos']), default=0) + 1,
                'title': caption, 'caption': caption, 'publishedAt': published, 'thumbnail': None, 'assetUrl': None, 'posts': {'youtube': post}})
            known[video_id] = post
            added += 1
        stats = entry.find('.//media:statistics', NS)
        views = stats.get('views') if stats is not None else None
        if observe and views is not None and re.fullmatch(r'\d+', views):
            observe(post, 'views', int(views), post['url'])
            post['metrics']['views'].update(method='public_channel_feed', evidenceUrl=feed_url)
    return added
