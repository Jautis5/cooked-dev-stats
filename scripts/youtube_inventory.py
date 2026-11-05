"""Owner-bound public YouTube video tabs, followed to their real pagination end.

No login, cookies, account credentials, media download or recommendation traversal.
Pagination cursors come only from the verified channel's own selected video tab.
"""
import datetime
import json
import re
import time
import urllib.request
from urllib.parse import parse_qs, urlsplit

import collect as base
from snapshot_merge import timestamp

VIDEO_TABS = {'videos', 'shorts', 'streams'}


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def initial(page):
    marker = re.search(r'(?:var\s+)?ytInitialData\s*=\s*', page)
    if not marker:
        raise ValueError('YouTube public channel data unavailable')
    return json.JSONDecoder().raw_decode(page[marker.end():])[0]


def tabs_of(value, channel):
    if value.get('metadata', {}).get('channelMetadataRenderer', {}).get('externalId') != channel:
        raise ValueError('YouTube channel owner mismatch')
    tabs = value.get('contents', {}).get('twoColumnBrowseResultsRenderer', {}).get('tabs')
    if not isinstance(tabs, list):
        raise ValueError('YouTube channel tabs unavailable')
    out = {}
    for wrapper in tabs:
        tab = wrapper.get('tabRenderer', {})
        endpoint = tab.get('endpoint', {})
        suffix = urlsplit(endpoint.get('commandMetadata', {}).get('webCommandMetadata', {}).get('url', '')).path.rstrip('/').rsplit('/', 1)[-1]
        if suffix not in VIDEO_TABS:
            continue
        if endpoint.get('browseEndpoint', {}).get('browseId') != channel:
            raise ValueError('YouTube video tab owner mismatch')
        out[suffix] = tab
    return out


def grid_items(content):
    for name, field in [('richGridRenderer', 'contents'), ('sectionListRenderer', 'contents'),
                        ('itemSectionRenderer', 'contents'), ('gridRenderer', 'items')]:
        if name in content:
            items = content[name].get(field)
            if not isinstance(items, list):
                raise ValueError('Invalid channel grid')
            return items
    raise ValueError('Unknown channel video grid')


def parse_items(items):
    found, cursors, unknown = [], [], False
    for wrapper in items:
        if not isinstance(wrapper, dict):
            unknown = True
            continue
        if 'continuationItemRenderer' in wrapper:
            tokens = [node['continuationCommand'].get('token') for node in base.walk(wrapper['continuationItemRenderer']) if isinstance(node.get('continuationCommand'), dict)]
            if len(tokens) != 1 or not isinstance(tokens[0], str) or not tokens[0]:
                unknown = True
            else:
                cursors.append(tokens[0])
            continue
        if any(name in wrapper for name in ['itemSectionRenderer', 'gridRenderer']):
            child, more, unparsed = parse_items(grid_items(wrapper))
            found.extend(child); cursors.extend(more); unknown |= unparsed
            continue
        content = wrapper.get('richItemRenderer', {}).get('content', wrapper)
        short = content.get('shortsLockupViewModel')
        video = content.get('videoRenderer') or content.get('gridVideoRenderer')
        if isinstance(short, dict):
            command = short.get('onTap', {}).get('innertubeCommand', {})
            identity = command.get('reelWatchEndpoint', {}).get('videoId', '')
            url = command.get('commandMetadata', {}).get('webCommandMetadata', {}).get('url')
            valid_url = url == '/shorts/' + identity
            title = short.get('overlayMetadata', {}).get('primaryText', {}).get('content')
        elif isinstance(video, dict):
            if video.get('isUpcoming') or video.get('upcomingEventData'):
                continue
            identity = video.get('videoId', '')
            command = video.get('navigationEndpoint', {})
            url = command.get('commandMetadata', {}).get('webCommandMetadata', {}).get('url', '')
            parts = urlsplit(url)
            valid_url = parts.path == '/watch' and parse_qs(parts.query).get('v') == [identity] and command.get('watchEndpoint', {}).get('videoId') == identity
            title = video.get('title', {}).get('simpleText') or ''.join(x.get('text', '') for x in video.get('title', {}).get('runs', []))
        else:
            # Unknown layouts cannot silently certify a complete inventory.
            unknown = True
            continue
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}', identity) or not valid_url:
            unknown = True
            continue
        found.append({'id': identity, 'url': 'https://www.youtube.com' + url, 'title': title or 'Untitled video'})
    return found, cursors, unknown


def continuation(items):
    # Only response actions appending to the requested browse grid are accepted.
    lists = []
    for name in ['onResponseReceivedActions', 'onResponseReceivedEndpoints']:
        for action in items.get(name, []):
            value = action.get('appendContinuationItemsAction', {}).get('continuationItems')
            if isinstance(value, list):
                lists.append(value)
    if len(lists) != 1:
        raise ValueError('YouTube continuation grid unavailable or ambiguous')
    return lists[0]


def browse(cursor, version):
    if not version or not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', version):
        raise ValueError('Public YouTube client version unavailable')
    body = json.dumps({'context': {'client': {'clientName': 'WEB', 'clientVersion': version, 'hl': 'en'}}, 'continuation': cursor}).encode()
    request = urllib.request.Request('https://www.youtube.com/youtubei/v1/browse', data=body,
        headers={'User-Agent': base.UA, 'Content-Type': 'application/json', 'Accept-Language': 'en-US,en;q=0.9'})
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.loads(response.read(5_000_000))


def verify_new(item, channel, request):
    page = request('https://www.youtube.com/watch?v=' + item['id'] + '&hl=en')
    marker = re.search(r'(?:var\s+)?ytInitialPlayerResponse\s*=\s*', page)
    player = json.JSONDecoder().raw_decode(page[marker.end():])[0] if marker else {}
    details = player.get('videoDetails', {})
    if details.get('videoId') != item['id'] or details.get('channelId') != channel:
        raise ValueError('New YouTube video owner unverified')
    if player.get('playabilityStatus', {}).get('status') != 'OK' or details.get('isPrivate') is True:
        raise ValueError('New YouTube video public visibility unverified')
    micro = player.get('microformat', {}).get('playerMicroformatRenderer', {})
    live_start = micro.get('liveBroadcastDetails', {}).get('startTimestamp')
    if timestamp(live_start) > datetime.datetime.now(datetime.timezone.utc).timestamp():
        raise ValueError('Scheduled YouTube video is not public content')
    published = micro.get('publishDate')
    # A calendar date alone does not establish a precise publication instant.
    try:
        parsed = datetime.datetime.fromisoformat(published.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            published = None
    except (AttributeError, TypeError, ValueError):
        published = None
    if timestamp(published) > datetime.datetime.now(datetime.timezone.utc).timestamp():
        raise ValueError('Scheduled YouTube video is not public content')
    return details.get('shortDescription') or details.get('title') or item['title'], published


def discover(data, account, request=None, request_page=None, max_pages=30):
    if type(max_pages) is not int or not 1 <= max_pages <= 100:
        raise ValueError('Invalid pagination limit')
    started = time.monotonic()
    request = request or base.request
    request_page = request_page or browse
    channel = account.get('expectedChannelId') or urlsplit(account['url']).path.rsplit('/', 1)[-1]
    if not re.fullmatch(r'UC[A-Za-z0-9_-]{22}', channel):
        raise ValueError('Unverified YouTube channel')
    source = 'https://www.youtube.com/channel/' + channel
    page = request(source + '?hl=en')
    home = initial(page)
    tabs = tabs_of(home, channel)
    if not tabs:
        texts = [node[k].lower() for node in base.walk(home) for k in ['text', 'simpleText'] if isinstance(node.get(k), str)]
        empty = any("channel doesn't have any content" in t or 'channel doesn’t have any content' in t or 'channel has no content' in t for t in texts)
        if not empty:
            raise ValueError('No authoritative public video tabs or empty state')
    seen, problems, pages = {}, [], 0
    for suffix, advertised in tabs.items():
        try:
            if advertised.get('selected'):
                tab, tab_page = advertised, page
            else:
                tab_page = request(source + '/' + suffix + '?hl=en')
                tab = tabs_of(initial(tab_page), channel).get(suffix)
                if not tab or tab.get('selected') is not True:
                    raise ValueError('Requested channel video tab not selected')
            version = re.search(r'"INNERTUBE_CLIENT_VERSION"\s*:\s*"([^"]+)"', tab_page)
            version = version[1] if version else None
            items, visited = grid_items(tab.get('content', {})), set()
            if not items:
                raise ValueError('Empty initial grid has no explicit terminal result')
            for number in range(max_pages):
                if time.monotonic() - started > 90:
                    raise ValueError('Inventory time budget reached before list end')
                rows, cursors, unknown = parse_items(items)
                pages += 1
                for row in rows:
                    seen[row['id']] = row
                if unknown:
                    problems.append(suffix + ':unparsed_grid')
                if not cursors:
                    break
                if len(cursors) != 1 or cursors[0] in visited:
                    raise ValueError('Pagination cursor repeated or ambiguous')
                if number + 1 == max_pages:
                    raise ValueError('Pagination safety limit reached before list end')
                visited.add(cursors[0])
                items = continuation(request_page(cursors[0], version))
        except Exception as error:
            problems.append(suffix + ':' + type(error).__name__)
    known = {str(v['posts']['youtube']['id']) for v in data['videos'] if 'youtube' in v['posts']}
    excluded = set(data.get('tracking', {}).get('excludedPostIds', {}).get('youtube', []))
    cutoff = timestamp(data.get('tracking', {}).get('startedAt'))
    scoped, added = set(), 0
    for identity, item in seen.items():
        if identity in excluded:
            continue
        if identity in known:
            scoped.add(identity)
            continue
        try:
            if time.monotonic() - started > 90:
                raise ValueError('Inventory metadata time budget reached')
            caption, published = verify_new(item, channel, request)
            if cutoff and not timestamp(published):
                raise ValueError('New video date insufficient for tracked scope')
            if cutoff and timestamp(published) < cutoff:
                continue
            data['videos'].append({'id': 'youtube-' + identity, 'number': max((v['number'] for v in data['videos']), default=0) + 1,
                'title': caption, 'caption': caption, 'publishedAt': published, 'thumbnail': None, 'assetUrl': None,
                'posts': {'youtube': {'id': identity, 'url': item['url'], 'metrics': {}}}})
            known.add(identity); scoped.add(identity); added += 1
        except Exception as error:
            problems.append('video:' + type(error).__name__)
    at = stamp()
    result = {'status': 'checked' if not problems else 'partial', 'method': 'public_youtube_inventory',
              'checkedAt': at, 'source': source, 'complete': not problems,
              'newVideos': added, 'listedPosts': len(scoped), 'pages': pages,
              'tabsChecked': sorted(tabs), 'scope': 'tracked_public_video_tabs'}
    if not problems:
        result.update(lastCompleteAt=at, lastCompletePostCount=len(scoped))
    else:
        result['paginationErrors'] = sorted(set(problems))
    return result
