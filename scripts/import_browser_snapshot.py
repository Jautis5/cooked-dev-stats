"""Merge a public-only browser feed bundle without local GitHub credentials."""
import copy, datetime, json, pathlib
import collect_channels
from publications import reconcile
from snapshot_merge import merge_snapshot, timestamp, validate
from refresh_all import metric_health

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPOSITORY = 'Jautis5/cooked-dev-stats'

def merge_bundle(root, bundle):
    root = pathlib.Path(root)
    if bundle.get('version') != 1 or bundle.get('repository') != REPOSITORY:
        raise ValueError('Wrong browser bundle repository')
    if not timestamp(bundle.get('startedAt')) or not timestamp(bundle.get('capturedAt')):
        raise ValueError('Missing actual browser observation interval')
    config = json.loads((root/'data/channels.json').read_text())['channels']
    by_id = {c['id']: c for c in config}
    incoming = bundle.get('channels', {})
    if not incoming or not set(incoming).issubset(by_id):
        raise ValueError('Browser bundle contains no channels or an unknown channel')
    ledger = json.loads((root/'data/publications.json').read_text())
    staged = {}
    for cid, candidate in incoming.items():
        c = by_id[cid]
        path = root/c['dataPath']
        current = json.loads(path.read_text()); candidate = copy.deepcopy(candidate)
        if candidate.get('channelId', 'cooked-dev') != cid:
            raise ValueError('Cross-channel snapshot rejected')
        expected = {a['id']: a['url'] for a in current['accounts']}
        if {a['id']: a['url'] for a in candidate['accounts']} != expected:
            raise ValueError('Account identity changed in browser bundle')
        validate(candidate); reconcile(current, ledger); reconcile(candidate, ledger)
        merged = merge_snapshot(current, candidate)
        reconcile(merged, ledger)
        merged['sourceUrl'] = 'https://github.com/' + REPOSITORY
        validate(merged); staged[cid] = (path, merged)
    # Validate every channel before making any data write.
    health = {'version':1, 'provider':'authorized_local_browser', 'trigger':'verified_browser_bundle',
              'startedAt':bundle['startedAt'], 'completedAt':bundle['capturedAt'],
              'intervalMinutes':15, 'status':'completed_with_gaps', 'channels':{}}
    for cid, (path, data) in staged.items():
        collect_channels.record(data, path.parent)
        platforms = metric_health(data, bundle['startedAt'])
        for platform, state in platforms.items():
            if data.get('discovery', {}).get(platform, {}).get('method') in ['browser_bulk','browser_profile']:
                state['access'] = 'authorized_browser'
        health['channels'][cid] = {'status':'completed_with_gaps', 'checkedAt':bundle['capturedAt'],
                                  'platforms':platforms, 'metricsUpdated':sum(p['metricsUpdated'] for p in platforms.values())}
    # Browser coverage must never replace the independent cloud collector report.
    health_path = root/'data/browser-health.json'
    previous = json.loads(health_path.read_text()) if health_path.exists() else {}
    if timestamp(health['completedAt']) > timestamp(previous.get('completedAt')):
        # Retain independently dated reports for registered channels absent from
        # this partial capture. Do not call their older metrics freshly checked.
        health['channels'] = {**previous.get('channels', {}), **health['channels']}
        health_path.write_text(json.dumps(health,ensure_ascii=False,indent=2)+'\n')
    return staged

if __name__ == '__main__':
    from publish_refresh import publish
    bundle = json.loads((ROOT/'incoming/browser-capture.json').read_text())
    merge_bundle(ROOT, bundle)
    print(json.dumps({'publishedCommit':publish(ROOT), 'repository':REPOSITORY}))
