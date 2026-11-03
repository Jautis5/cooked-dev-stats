"""Merge public observations by measurement time, preserving concurrent source edits."""
import copy, datetime, math


def timestamp(value):
    try:
        return datetime.datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
    except (AttributeError, TypeError, ValueError):
        return 0


def newer(left, right):
    return left if timestamp(left) >= timestamp(right) else right


def merge_channel_health(remote, collected):
    """Retain independently dated channel reports across partial browser bundles."""
    out = copy.deepcopy(collected if timestamp(collected.get('completedAt')) > timestamp(remote.get('completedAt')) else remote)
    reports = copy.deepcopy(remote.get('channels', {}))
    for cid, report in collected.get('channels', {}).items():
        if timestamp(report.get('checkedAt')) >= timestamp(reports.get(cid, {}).get('checkedAt')):
            reports[cid] = copy.deepcopy(report)
    if reports or 'channels' in remote or 'channels' in collected:
        out['channels'] = reports
    return out


def merge_discovery(remote, collected):
    """Keep explicit completeness revocations through stale and concurrent replay."""
    selected = copy.deepcopy(collected if timestamp(collected.get('checkedAt')) > timestamp(remote.get('checkedAt')) else remote)
    revoked = {}
    for report in (remote, collected):
        records = report.get('revokedCompleteChecks', [])
        if not isinstance(records, list):
            raise ValueError('Invalid completeness revocations')
        for record in records:
            if not isinstance(record, dict) or set(record) - {'at', 'recordedAt', 'fallbackAt', 'fallbackPostCount', 'reason'}:
                raise ValueError('Invalid completeness revocation')
            for key in ('at', 'recordedAt', 'fallbackAt'):
                try:
                    valid = datetime.datetime.fromisoformat(record[key].replace('Z', '+00:00')).tzinfo is not None
                except (KeyError, AttributeError, TypeError, ValueError):
                    valid = False
                if not valid or not timestamp(record.get(key)):
                    raise ValueError('Invalid completeness revocation date')
            if timestamp(record['fallbackAt']) >= timestamp(record['at']) or timestamp(record['recordedAt']) < timestamp(record['at']):
                raise ValueError('Invalid completeness revocation interval')
            if not isinstance(record.get('reason'), str) or not 1 <= len(record['reason']) <= 240:
                raise ValueError('Missing public completeness correction reason')
            if 'fallbackPostCount' in record and (type(record['fallbackPostCount']) is not int or record['fallbackPostCount'] < 0):
                raise ValueError('Invalid fallback publication count')
            key = timestamp(record['at'])
            rank = lambda r: (timestamp(r['recordedAt']), timestamp(r['fallbackAt']), r['reason'], r.get('fallbackPostCount', -1), r['at'], r['recordedAt'], r['fallbackAt'])
            if key not in revoked or rank(record) > rank(revoked[key]):
                revoked[key] = copy.deepcopy(record)
    if not revoked:
        complete_at = newer(collected.get('lastCompleteAt'), remote.get('lastCompleteAt'))
        if complete_at: selected['lastCompleteAt'] = complete_at
        return selected
    candidates = []
    for report in (remote, collected):
        at = report.get('lastCompleteAt')
        if timestamp(at) and timestamp(at) not in revoked:
            candidates.append((timestamp(at), 1, timestamp(report.get('checkedAt')), at, report.get('lastCompletePostCount')))
    for record in revoked.values():
        at = record['fallbackAt']
        if timestamp(at) not in revoked:
            candidates.append((timestamp(at), 0, timestamp(record['recordedAt']), at, record.get('fallbackPostCount')))
    if selected.get('complete') is True and (timestamp(selected.get('checkedAt')) in revoked or timestamp(selected.get('lastCompleteAt')) in revoked):
        selected['complete'] = False
        selected['status'] = 'partial'
    selected.pop('lastCompleteAt', None)
    selected.pop('lastCompletePostCount', None)
    if candidates:
        chosen = max(candidates, key=lambda item: (item[0], type(item[4]) is int and item[4] >= 0, *item[1:4]))
        selected['lastCompleteAt'] = chosen[3]
        if type(chosen[4]) is int and chosen[4] >= 0:
            selected['lastCompletePostCount'] = chosen[4]
    selected['revokedCompleteChecks'] = [revoked[key] for key in sorted(revoked)]
    return selected


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
        out['discovery'][platform] = merge_discovery(prior, report)
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
