"""Reconcile explicitly verified publication identities, never caption similarity.

The ledger is replayed on every collection and concurrent publish. This makes a
verified upload durable even when a platform's unauthenticated list is blocked.
"""
import copy, json, pathlib, re
from urllib.parse import parse_qs, urlsplit
from snapshot_merge import timestamp

ROOT = pathlib.Path(__file__).resolve().parents[1]


def publication_id(platform, url, account):
    u = urlsplit(url)
    if u.scheme != 'https':
        raise ValueError('HTTPS publication required')
    parts = u.path.strip('/').split('/')
    handle = account.get('expectedHandle') or account.get('handle')
    if platform == 'youtube' and u.hostname in ['youtube.com', 'www.youtube.com']:
        identity = parse_qs(u.query).get('v', [''])[0] if u.path == '/watch' else parts[-1] if parts[0] == 'shorts' else ''
        if re.fullmatch(r'[A-Za-z0-9_-]{11}', identity): return identity
    if platform == 'instagram' and u.hostname in ['instagram.com', 'www.instagram.com']:
        if len(parts) == 3 and parts[0].lower() == handle.lower() and parts[1] in ['reel', 'p']: return parts[2]
        if len(parts) == 2 and parts[0] in ['reel', 'p']: return parts[1]
    if platform == 'tiktok' and u.hostname in ['tiktok.com', 'www.tiktok.com'] and len(parts) == 3:
        if parts[0] == '@' + handle and parts[1] == 'video' and parts[2].isdigit(): return parts[2]
    if platform == 'x' and u.hostname in ['x.com', 'www.x.com'] and len(parts) == 3:
        if parts[0].lower() == handle.lower() and parts[1] == 'status' and parts[2].isdigit(): return parts[2]
    if platform == 'facebook' and u.hostname in ['facebook.com', 'www.facebook.com']:
        if len(parts) == 2 and parts[0] == 'reel' and parts[1].isdigit(): return parts[1]
    raise ValueError('Publication URL does not match its platform/account')


def reconcile(data, ledger=None):
    if ledger is None:
        path = ROOT / 'data/publications.json'
        ledger = json.loads(path.read_text()) if path.exists() else {'groups': []}
    accounts = {a['id']: a for a in data['accounts']}
    for group in ledger.get('groups', []):
        if group['channelId'] != data.get('channelId', 'cooked-dev'): continue
        if not timestamp(group.get('verifiedAt')) or not group.get('evidence'):
            raise ValueError('Publication group requires dated evidence')
        identities = {p: publication_id(p, url, accounts[p]) for p, url in group['posts'].items()}
        if any(p in ['youtube', 'facebook'] and p not in group.get('owners', {}) for p in identities):
            raise ValueError('Channel/Page owner evidence is required')
        for platform, owner in group.get('owners', {}).items():
            account = accounts[platform]
            expected = (account.get('expectedChannelId') or urlsplit(account['url']).path.rstrip('/').split('/')[-1]) if platform == 'youtube' else (account.get('expectedPageId') or parse_qs(urlsplit(account['url']).query).get('id', [''])[0]) if platform == 'facebook' else account.get('expectedHandle') or account.get('handle')
            if str(expected).lower() != str(owner).lower(): raise ValueError('Ledger owner mismatch')
        matches = [v for v in data['videos'] if v['id'] == group['videoId'] or any(str(v['posts'].get(p, {}).get('id')) == identity for p, identity in identities.items())]
        target = next((v for v in matches if v['id'] == group['videoId']), matches[0] if matches else None)
        if target is None:
            target = {'id': group['videoId'], 'number': max((v['number'] for v in data['videos']), default=0)+1,
                      'title': group['caption'], 'caption': group['caption'], 'publishedAt': group.get('publishedAt'),
                      'thumbnail': None, 'assetUrl': None, 'posts': {}}
            data['videos'].append(target)
        for other in matches:
            if other is target: continue
            # A registry mistake must never silently overwrite another publication.
            for platform, post in other['posts'].items():
                old = target['posts'].get(platform)
                if old and str(old['id']) != str(post['id']): raise ValueError('Conflicting publications in one video group')
                if not old: target['posts'][platform] = copy.deepcopy(post)
                else:
                    for key, metric in post.get('metrics', {}).items():
                        if timestamp(metric.get('at')) > timestamp(old.get('metrics', {}).get(key, {}).get('at')):
                            measurement = copy.deepcopy(metric)
                            if measurement.get('source') != old['url']:
                                measurement.setdefault('evidenceUrl', measurement.get('source'))
                                measurement['source'] = old['url']
                            old.setdefault('metrics', {})[key] = measurement
            data['videos'].remove(other)
        for platform, identity in identities.items():
            post = target['posts'].get(platform)
            if post and str(post['id']) != identity: raise ValueError('Ledger conflicts with a verified publication')
            if not post:
                post = target['posts'][platform] = {'id': identity, 'url': group['posts'][platform], 'metrics': {}}
            post['publicationVerifiedAt'] = max([group['verifiedAt'], post.get('publicationVerifiedAt', group['verifiedAt'])], key=timestamp)
            post['verificationEvidence'] = group['evidence']
        if group.get('assetUrl'): target['assetUrl'] = group['assetUrl']
        target['publicationGroupId'] = group['id']
    numbers = {g['id']:g['number'] for g in ledger.get('groups', []) if g.get('number') and g['channelId'] == data.get('channelId','cooked-dev')}
    for video in data['videos']:
        if video.get('publicationGroupId') in numbers: video['number'] = numbers[video['publicationGroupId']]
    if len({v['number'] for v in data['videos']}) != len(data['videos']): raise ValueError('Conflicting canonical video numbers')
    # Discovery of any real post invalidates a historical empty-account claim.
    for account in data['accounts']:
        posts = [v['posts'][account['id']] for v in data['videos'] if account['id'] in v['posts']]
        if posts:
            account.pop('trackedEmptyConfirmedAt', None)
            account.pop('emptyConfirmedAt', None)
            if account.get('metrics', {}).get('trackedPublishedCount', {}).get('value', 1) == 0:
                account['metrics'].pop('trackedPublishedCount')
            if account.get('metrics', {}).get('publishedCount', {}).get('value', 1) == 0:
                account['metrics'].pop('publishedCount')
    return data
