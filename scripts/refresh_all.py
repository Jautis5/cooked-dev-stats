"""Unattended cloud collection with optional official reads. No local browser."""
import copy, datetime, json, os, pathlib, sys
import collect as base
import collect_channels as extra
from snapshot_merge import validate, timestamp
from publications import reconcile
from inventory_health import inventory_health
from public_fallbacks import refresh_fallbacks
import official_broker
ROOT = pathlib.Path(__file__).resolve().parents[1]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def metric_health(data, observed_at):
    def fresh(metric):
        return timestamp(metric.get('at')) >= timestamp(observed_at)
    out = {}
    for account in data['accounts']:
        objects = [account] + [v['posts'][account['id']] for v in data['videos'] if account['id'] in v['posts']]
        metrics = [m for obj in objects for m in obj.get('metrics', {}).values()]
        views = [obj.get('metrics', {}).get('views') for obj in objects[1:]]
        inventory = data.get('discovery', {}).get(account['id'], {})
        keys = {'views', 'likes', 'comments', 'shares'} | {k for obj in objects[1:] for k in obj.get('metrics', {})}
        coverage = {}
        for key in sorted(keys):
            known = [obj.get('metrics', {}).get(key) for obj in objects[1:]]
            known = [m for m in known if m and base.num(m.get('value')) is not None]
            coverage[key] = {'known': len(known), 'updated': sum(fresh(m) for m in known),
                             'missing': len(objects)-1-len(known),
                             'oldestAt': min((m['at'] for m in known), key=timestamp, default=None)}
        out[account['id']] = {
            'name': account['name'], 'status': account['status'],
            'metricsUpdated': sum(fresh(m) for m in metrics),
            'metricsKnown': len(metrics),
            'viewsUpdated': sum(fresh(obj.get('metrics', {}).get('views', {})) for obj in objects[1:]),
            'postsKnown': len(objects)-1,
            'viewsKnown': sum(bool(m) for m in views),
            'metricCoverage': coverage,
            'oldestViewAt': min((m['at'] for m in views if m), key=timestamp, default=None),
            'inventoryStatus': inventory.get('status', 'unverified'),
            'inventoryComplete': inventory.get('complete') is True,
            'inventoryCheckedAt': inventory.get('checkedAt'),
            'inventoryAudit': inventory_health(data, account, observed_at),
            'reportedPostCount': account.get('metrics', {}).get('publishedCount'),
            'latestMetricAt': max((m['at'] for m in metrics), key=timestamp, default=None),
            'access': 'authorized_cloud' if inventory.get('method') == 'official_api' else 'authorization_required' if account['id'] in ['instagram','facebook'] and inventory.get('status') == 'session_required' else 'public_cloud',
        }
    return out


def refresh(root=ROOT):
    policy = json.loads((root / 'data/collection-policy.json').read_text())
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    base.NOW = started
    run_url = None
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        run_url = 'https://github.com/' + os.environ['GITHUB_REPOSITORY'] + '/actions/runs/' + os.environ['GITHUB_RUN_ID']
    health = {'version': 1, 'startedAt': started, 'provider': 'GitHub Actions' if run_url else 'local_verification', 'trigger': os.environ.get('GITHUB_EVENT_NAME', 'unknown') if run_url else 'local_verification', 'intervalMinutes': policy['intervalMinutes'], 'runUrl': run_url, 'channels': {}}
    initiator = os.environ.get('COLLECTION_INITIATOR','unknown') if run_url else 'local_verification'
    health['initiator'] = initiator if initiator in ['manual','continuous_clock','watchdog','schedule','local_verification'] else 'unknown'
    clock_id = os.environ.get('COLLECTION_CLOCK_RUN_ID','')
    if run_url and initiator=='continuous_clock' and clock_id.isdecimal():
        health['clockRunUrl']='https://github.com/'+os.environ['GITHUB_REPOSITORY']+'/actions/runs/'+clock_id
    health['clockDriver']=policy.get('clockDriver') if policy.get('continuousClockEnabled') else None
    failed = 0
    for config in json.loads((root / 'data/channels.json').read_text())['channels']:
        path = (root / config['dataPath']).resolve()
        if not path.is_relative_to((root / 'data').resolve()):
            raise ValueError('Unsafe channel data path')
        previous = json.loads(path.read_text())
        try:
            prepared = reconcile(copy.deepcopy(previous))
            data = base.collect(prepared) if config['id'] == 'cooked-dev' else extra.refresh(prepared)
            refresh_fallbacks(data)
            official_broker.refresh(data)
            reconcile(data)
            # Include fallback measurements in the same run's actual update count.
            data['cloudCollection']['metricsUpdated'] = {p:h['metricsUpdated'] for p,h in metric_health(data, started).items()}
            data['schedule'] = {'provider': 'GitHub Actions' if run_url else 'local_verification', 'intervalMinutes': policy['intervalMinutes'], 'cron': policy['cron']}
            data['cloudCollection']['runUrl'] = run_url
            validate(data)
            if config['id'] == 'cooked-dev':
                base.exports(data, path.parent)
                base.archive(data, path.parent)
                base.update_changes(data, directory=path.parent)
                write_json(path, data)
            else:
                extra.record(data, path.parent)
            platforms = metric_health(data, started)
            health['channels'][config['id']] = {'status': 'completed', 'checkedAt': started, 'platforms': platforms, 'metricsUpdated': sum(a['metricsUpdated'] for a in platforms.values())}
            print(json.dumps({'channel': config['id'], 'metricsUpdated': health['channels'][config['id']]['metricsUpdated'], 'platforms': platforms}))
        except Exception as error:
            failed += 1
            write_json(path, previous)
            health['channels'][config['id']] = {'status': 'failed', 'checkedAt': started, 'error': type(error).__name__, 'platforms': metric_health(previous, started), 'metricsUpdated': 0}
            print('::warning::Cloud collection failed for ' + config['id'] + '; original metric dates retained.')
    health['completedAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    health['inventoryAttentionRequired'] = any(p['inventoryAudit']['overdue'] for c in health['channels'].values() for p in c['platforms'].values())
    gaps = any(not p.get('inventoryComplete') or (p['postsKnown'] and p['viewsUpdated'] < p['postsKnown'])
               for channel in health['channels'].values() for p in channel['platforms'].values())
    health['status'] = 'completed_with_errors' if failed else 'completed_with_gaps' if gaps else 'completed'
    write_json(root / 'data/health.json', health)
    return failed


if __name__ == '__main__':
    sys.exit(1 if refresh() else 0)
