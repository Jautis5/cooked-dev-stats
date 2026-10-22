"""Bounded, anonymous FxEmbed reads. Third-party observations are labelled explicitly."""
import datetime
import json
import re
import urllib.parse

import collect as base

API = 'https://api.fxtwitter.com/2/'


def get(path):
    response = json.loads(base.request(API + path))
    if response.get('code') != 200:
        raise ValueError('FxEmbed did not return a successful observation')
    return response


def handle_of(account):
    handle = account.get('expectedHandle') or account.get('handle', '')
    if not re.fullmatch(r'[A-Za-z0-9_]{1,15}', handle):
        raise ValueError('Invalid registered X handle')
    return handle


def owned_video(item, handle, identity=None):
    author = item.get('author') or {}
    identity = identity or str(item.get('id', ''))
    if (not identity.isdecimal() or str(item.get('id')) != identity
            or author.get('screen_name', '').lower() != handle.lower()
            or author.get('protected') is not False or item.get('reposted_by')
            or item.get('type') != 'status'):
        return False
    # Inspect only attached media; a quoted or recommended video is not this post's video.
    return any(m.get('type') == 'video' for m in (item.get('media') or {}).get('all', []))


def observe(obj, key, value, endpoint):
    # Do not coerce booleans, rounded text, floats, missing values or negative counters.
    if type(value) is not int or value < 0:
        return
    base.setmetric(obj, key, value, obj['url'])
    obj['metrics'][key].update(method='fxembed_public', via=API + endpoint,
                               upstreamObservedAt=None)


def post_metrics(post, item, endpoint):
    for key, field in [('views', 'views'), ('likes', 'likes'),
                       ('comments', 'replies'), ('shares', 'reposts')]:
        observe(post, key, item.get(field), endpoint)


def known_post(post, account):
    endpoint = 'status/' + post['id']
    item = get(endpoint).get('status') or {}
    if not owned_video(item, handle_of(account), post['id']):
        raise ValueError('FxEmbed X video or owner unverified')
    post_metrics(post, item, endpoint)
    return post


def discover(data, account, add_post):
    handle = handle_of(account)
    profile_endpoint = 'profile/' + handle
    profile = get(profile_endpoint).get('user') or {}
    if (profile.get('screen_name', '').lower() != handle.lower()
            or profile.get('protected') is not False
            or not str(profile.get('id', '')).isdecimal()):
        raise ValueError('FxEmbed X profile owner unverified')
    observe(account, 'followers', profile.get('followers'), profile_endpoint)
    before = len(data['videos'])
    listed = set()
    cursor = None
    seen_cursors = set()
    error = None
    pages = 0
    # A stable numeric owner ID avoids stale handle-to-timeline responses.
    for _ in range(3):
        endpoint = 'profile/id:' + str(profile['id']) + '/media?count=100'
        if cursor:
            endpoint += '&cursor=' + urllib.parse.quote(cursor, safe='')
        try:
            response = get(endpoint)
        except Exception as failure:
            error = type(failure).__name__
            break
        if not isinstance(response.get('results'), list):
            error = 'InvalidTimeline'
            break
        pages += 1
        for item in response['results']:
            if not isinstance(item, dict) or not owned_video(item, handle):
                continue
            identity = str(item['id'])
            listed.add(identity)
            # Epoch from the service must be valid before admitting an unknown post.
            epoch = item.get('created_timestamp')
            try:
                published = datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).isoformat() if type(epoch) is int else None
            except (ValueError, OverflowError, OSError):
                published = None
            if not published:
                continue
            url = 'https://x.com/' + handle + '/status/' + identity
            post = add_post(data, 'x', identity, url, item.get('text') or 'Untitled video', published)
            if post:
                post_metrics(post, item, endpoint)
        next_cursor = (response.get('cursor') or {}).get('bottom')
        if not response['results'] or not next_cursor or next_cursor in seen_cursors:
            break
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    if not pages:
        raise ValueError('FxEmbed timeline unavailable; previous inventory retained')
    result = {'status': 'partial', 'method': 'fxembed_public',
              'newVideos': len(data['videos']) - before, 'listedPosts': len(listed),
              'pages': pages, 'complete': False,
              'message': 'Third-party public timeline; upstream completeness and cache age are not guaranteed.'}
    if error:
        result['paginationError'] = error
    return result
