"""Merge public observations by measurement time, preserving concurrent source edits."""
import copy, datetime, math


def timestamp(value):
    try:
        return datetime.datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
    except (AttributeError, TypeError, ValueError):
        return 0


def newer(left, right):
    return left if timestamp(left) >= timestamp(right) else right


def merge_object(remote, collected):
    out = copy.deepcopy(remote)
    if str(remote.get('id')) != str(collected.get('id')):
        raise ValueError('Observation identity mismatch')
    if remote.get('url') != collected.get('url'):
        return out
    if timestamp(collected.get('lastAttemptAt')) > timestamp(remote.get('lastAttemptAt')):
        for key in ['lastAttemptAt', 'status', 'message', 'emptyConfirmedAt', 'trackedEmptyConfirmedAt']:
            if key in collected:
                out[key] = copy.deepcopy(collected[key])
    if collected.get('lastSuccessAt'):
        out['lastSuccessAt'] = newer(collected['lastSuccessAt'], remote.get('lastSuccessAt'))
    for key, metric in collected.get('metrics', {}).items():
        value = metric.get('value')
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            continue
        if metric.get('source') != out.get('url') or not timestamp(metric.get('at')):
            continue
        prior = out.setdefault('metrics', {}).get(key, {})
        if timestamp(metric['at']) > timestamp(prior.get('at')):
            out['metrics'][key] = copy.deepcopy(metric)
    return out


def merge_snapshot(remote, collected, baseline=None):
    if remote.get('channelId') != collected.get('channelId'):
        raise ValueError('Channel identity mismatch')
    out = copy.deepcopy(remote)
    base_ids = {v['id'] for v in (baseline or {}).get('videos', [])}
    account_map = {a['id']: a for a in collected['accounts']}
    out['accounts'] = [merge_object(a, account_map[a['id']]) if a['id'] in account_map else a for a in out['accounts']]
    videos = {v['id']: v for v in out['videos']}
    seen = {(platform, str(p['id'])) for v in out['videos'] for platform, p in v['posts'].items()}
    numbers = {v.get('number') for v in out['videos']}
    for video in collected['videos']:
        target = videos.get(video['id'])
        if target is None:
            # A record deliberately removed since collection began must not be resurrected.
            if video['id'] in base_ids:
                continue
            fresh = copy.deepcopy(video)
            fresh['posts'] = {platform: p for platform, p in fresh['posts'].items() if (platform, str(p['id'])) not in seen}
            if not fresh['posts']:
                continue
            if fresh.get('number') in numbers or fresh.get('number') is None:
                fresh['number'] = max((n for n in numbers if isinstance(n, int)), default=0) + 1
            numbers.add(fresh['number'])
            out['videos'].append(fresh)
            videos[fresh['id']] = fresh
            seen.update((platform, str(p['id'])) for platform, p in fresh['posts'].items())
            continue
        base_video = next((v for v in (baseline or {}).get('videos', []) if v['id'] == video['id']), {})
        for key in ['assetUrl', 'title', 'caption', 'publishedAt', 'thumbnail']:
            if key in video and video.get(key) != base_video.get(key) and target.get(key) == base_video.get(key):
                target[key] = copy.deepcopy(video[key])
        for platform, post in video['posts'].items():
            if platform in target['posts']:
                if str(target['posts'][platform]['id']) == str(post['id']):
                    target['posts'][platform] = merge_object(target['posts'][platform], post)
            elif (platform, str(post['id'])) not in seen:
                # Retain a deliberate removal of an existing platform link.
                base_video = next((v for v in (baseline or {}).get('videos', []) if v['id'] == video['id']), {})
                if platform in base_video.get('posts', {}):
                    continue
                target['posts'][platform] = copy.deepcopy(post)
                seen.add((platform, str(post['id'])))
    for key in ['lastAttemptAt', 'generatedAt']:
        if collected.get(key):
            out[key] = newer(collected[key], out.get(key))
    for platform, report in collected.get('discovery', {}).items():
        prior = out.setdefault('discovery', {}).get(platform, {})
        selected = copy.deepcopy(report if timestamp(report.get('checkedAt')) > timestamp(prior.get('checkedAt')) else prior)
        complete_at = newer(report.get('lastCompleteAt'), prior.get('lastCompleteAt'))
        if complete_at: selected['lastCompleteAt'] = complete_at
        out['discovery'][platform] = selected
    if timestamp(collected.get('cloudCollection', {}).get('at')) > timestamp(out.get('cloudCollection', {}).get('at')):
        out['cloudCollection'] = copy.deepcopy(collected['cloudCollection'])
        out['schedule'] = copy.deepcopy(collected.get('schedule', out.get('schedule', {})))
    history = {h['at']: h for h in collected.get('history', [])}
    history.update({h['at']: h for h in remote.get('history', [])})
    out['history'] = sorted(history.values(), key=lambda h: timestamp(h['at']))[-2160:]
    return out


def validate(data):
    if data.get('version') != 1 or not isinstance(data.get('accounts'), list) or not isinstance(data.get('videos'), list):
        raise ValueError('Invalid snapshot schema')
    if len({a['id'] for a in data['accounts']}) != len(data['accounts']):
        raise ValueError('Duplicate account')
    if len({v['id'] for v in data['videos']}) != len(data['videos']):
        raise ValueError('Duplicate video')
    seen = set()
    for obj in data['accounts'] + [p for v in data['videos'] for p in v['posts'].values()]:
        if not obj['url'].startswith('https://'):
            raise ValueError('Invalid source URL')
        for metric in obj.get('metrics', {}).values():
            value = metric.get('value')
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or not timestamp(metric.get('at')) or metric.get('source') != obj['url']:
                raise ValueError('Invalid public metric')
    for v in data['videos']:
        for platform, post in v['posts'].items():
            key = (platform, str(post['id']))
            if key in seen:
                raise ValueError('Duplicate publication')
            seen.add(key)
