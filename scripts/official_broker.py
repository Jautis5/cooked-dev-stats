"""Optional official-account observations. The hosted broker never returns tokens."""
import copy
import concurrent.futures
import datetime
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import urllib.parse
import urllib.request

import collect as base
from public_fallbacks import add_post
from snapshot_merge import timestamp

PLATFORMS = ['youtube', 'tiktok', 'instagram', 'facebook']


def request(channel, platform, known_ids, url, signing_key):
    if not re.fullmatch(r'https://script\.google\.com/macros/s/[A-Za-z0-9_-]+/exec', url):
        raise ValueError('Invalid official broker URL')
    if len(signing_key) < 32:
        raise ValueError('Invalid official broker signing key')
    message = json.dumps([1, 'collect', int(time.time()), secrets.token_hex(16), channel, platform, known_ids], ensure_ascii=False, separators=(',', ':'))
    payload = json.dumps({'message': message, 'signature': hmac.new(signing_key.encode(), message.encode(), hashlib.sha256).hexdigest()}).encode()
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json', 'User-Agent': 'Social-Stats-Official-Reader'})
    with urllib.request.urlopen(req, timeout=120) as response:
        value = json.loads(response.read(5_000_000))
    if value.get('ok') is not True:
        allowed = {'CONFIGURATION_REQUIRED', 'UNAUTHORIZED', 'RECONNECT_REQUIRED', 'IDENTITY_MISMATCH', 'SOURCE_UNAVAILABLE', 'REPLAY_REJECTED'}
        raise ValueError(value.get('error') if value.get('error') in allowed else 'SOURCE_UNAVAILABLE')
    return value['observation']


def owner(account):
    platform = account['id']
    if platform in ['instagram', 'tiktok']:
        return {'handle': account.get('expectedHandle') or account.get('handle')}
    if platform == 'youtube':
        return {'id': account.get('expectedChannelId') or account['url'].rstrip('/').split('/')[-1]}
    return {'id': account.get('expectedPageId') or urllib.parse.parse_qs(urllib.parse.urlsplit(account['url']).query).get('id', [None])[0]}


def valid_post(platform, post, identity):
    post_id = post.get('id', '')
    if not isinstance(post_id, str):
        return False
    url = urllib.parse.urlsplit(post.get('url', ''))
    if url.scheme != 'https' or url.query and platform != 'youtube' or url.fragment:
        return False
    if platform == 'instagram':
        return bool(re.fullmatch(r'[A-Za-z0-9_-]+', post_id)) and url.netloc == 'www.instagram.com' and url.path.rstrip('/') in ['/reel/' + post_id, '/p/' + post_id]
    if platform == 'tiktok':
        return post_id.isdecimal() and url.netloc == 'www.tiktok.com' and url.path == '/@' + identity['handle'] + '/video/' + post_id
    if platform == 'facebook':
        return post_id.isdecimal() and url.netloc == 'www.facebook.com' and url.path == '/reel/' + post_id
    return bool(re.fullmatch(r'[A-Za-z0-9_-]{11}', post_id)) and url.netloc == 'www.youtube.com' and ((url.path == '/watch' and urllib.parse.parse_qs(url.query) == {'v': [post_id]}) or url.path == '/shorts/' + post_id)


def metrics(target, incoming, at):
    for key, value in incoming.items():
        if key not in ['views', 'likes', 'comments', 'shares', 'saves', 'followers', 'profileLikes', 'publishedCount'] or not isinstance(value, dict):
            continue
        count = value.get('value')
        if type(count) is not int or count < 0:
            continue
        field = value.get('apiMetric', '')
        if not isinstance(field, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]{0,63}', field):
            continue
        prior = target.get('metrics', {}).get(key, {})
        if timestamp(prior.get('at')) > timestamp(at):
            continue
        target.setdefault('metrics', {})[key] = {'value': count, 'at': at, 'source': target['url'], 'approximate': value.get('approximate') is True,
                                                'method': 'official_api', 'apiMetric': field}


def apply(data, platform, observation):
    channel = data.get('channelId', 'cooked-dev')
    account = next(a for a in data['accounts'] if a['id'] == platform)
    expected = owner(account)
    at = observation.get('checkedAt')
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    if (observation.get('version') != 1 or observation.get('channelId') != channel or observation.get('platform') != platform
            or observation.get('owner') != expected or not timestamp(at) or not now - 600 <= timestamp(at) <= now + 120):
        raise ValueError('Official observation identity or time unverified')
    posts = observation.get('posts')
    if not isinstance(posts, list) or len(posts) > 1300:
        raise ValueError('Invalid official publication list')
    seen = set()
    for post in posts:
        if not isinstance(post, dict) or not valid_post(platform, post, expected) or post['id'] in seen or not timestamp(post.get('publishedAt')):
            raise ValueError('Invalid official publication')
        if timestamp(post['publishedAt']) > timestamp(at) + 120:
            raise ValueError('Future publication cannot be public evidence')
        seen.add(post['id'])
    # Validate the whole response before changing the snapshot.
    target = copy.deepcopy(data)
    account = next(a for a in target['accounts'] if a['id'] == platform)
    metrics(account, observation.get('accountMetrics', {}), at)
    before = len(target['videos'])
    cutoff = timestamp(target.get('tracking', {}).get('startedAt')) or min((timestamp(v.get('publishedAt')) for v in target['videos'] if timestamp(v.get('publishedAt'))), default=0)
    excluded = set(target.get('tracking', {}).get('excludedPostIds', {}).get(platform, []))
    for post in posts:
        if post['id'] in excluded:
            continue
        existing = next((v['posts'][platform] for v in target['videos'] if str(v['posts'].get(platform, {}).get('id')) == post['id']), None)
        if existing is None and cutoff and timestamp(post['publishedAt']) < cutoff:
            continue
        existing = existing or add_post(target, platform, post['id'], post['url'], post.get('title') or 'Untitled video', post['publishedAt'])
        if existing:
            metrics(existing, post.get('metrics', {}), at)
    report = observation.get('inventory', {})
    complete = report.get('complete') is True and report.get('scope') == 'since_tracking_start'
    target.setdefault('discovery', {})[platform] = {'status': 'complete' if complete else 'partial', 'method': 'official_api', 'complete': complete,
        'checkedAt': at, 'listedPosts': len(posts), 'newVideos': len(target['videos']) - before}
    previous_complete = data.get('discovery', {}).get(platform, {}).get('lastCompleteAt')
    if complete or previous_complete:
        target['discovery'][platform]['lastCompleteAt'] = at if complete else previous_complete
    account.update(lastAttemptAt=at, lastSuccessAt=at, status='partial', message='Official account data refreshed; missing metrics retain their previous dates.')
    data.clear()
    data.update(target)


def refresh(data):
    url, key = os.environ.get('SOCIAL_STATS_BROKER_URL'), os.environ.get('SOCIAL_STATS_BROKER_KEY')
    if not url or not key:
        return data
    channel = data.get('channelId', 'cooked-dev')
    # Bound a stalled provider to one timeout per channel, preserving the working public pass.
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        pending = {platform: executor.submit(request, channel, platform,
                   [str(v['posts'][platform]['id']) for v in data['videos'] if platform in v['posts']], url, key)
                   for platform in PLATFORMS}
        for platform, future in pending.items():
            try:
                apply(data, platform, future.result())
            except Exception:
                # Never print third-party response bodies, URLs, secrets or account tokens.
                print('::notice::Official ' + platform + ' connection not ready for ' + channel + '; prior observations retained.')
    return data
