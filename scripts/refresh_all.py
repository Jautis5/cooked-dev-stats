"""Unattended cloud collection. No browser, Codex, OAuth files or owner computer."""
import copy, datetime, json, os, pathlib, sys
import collect as base
import collect_channels as extra
from snapshot_merge import validate, timestamp
ROOT = pathlib.Path(__file__).resolve().parents[1]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def metric_health(data, observed_at):
    out = {}
    for account in data['accounts']:
        objects = [account] + [v['posts'][account['id']] for v in data['videos'] if account['id'] in v['posts']]
        metrics = [m for obj in objects for m in obj.get('metrics', {}).values()]
        out[account['id']] = {
            'name': account['name'], 'status': account['status'],
            'metricsUpdated': sum(m.get('at') == observed_at for m in metrics),
            'latestMetricAt': max((m['at'] for m in metrics), key=timestamp, default=None),
            'access': 'authorization_required' if account['id'] in ['facebook', 'x'] and account['status'] == 'unavailable' else 'public_cloud',
        }
    return out


def refresh(root=ROOT):
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    base.NOW = started
    run_url = None
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        run_url = 'https://github.com/' + os.environ['GITHUB_REPOSITORY'] + '/actions/runs/' + os.environ['GITHUB_RUN_ID']
    health = {'version': 1, 'startedAt': started, 'provider': 'GitHub Actions' if run_url else 'local_verification', 'intervalMinutes': 30, 'runUrl': run_url, 'channels': {}}
    failed = 0
    for config in json.loads((root / 'data/channels.json').read_text())['channels']:
        path = (root / config['dataPath']).resolve()
        if not path.is_relative_to((root / 'data').resolve()):
            raise ValueError('Unsafe channel data path')
        previous = json.loads(path.read_text())
        try:
            data = base.collect(copy.deepcopy(previous)) if config['id'] == 'cooked-dev' else extra.refresh(copy.deepcopy(previous))
            data['schedule'] = {'provider': 'GitHub Actions' if run_url else 'local_verification', 'intervalMinutes': 30, 'cron': '13,43 * * * *'}
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
    health['status'] = 'completed_with_errors' if failed else 'completed'
    write_json(root / 'data/health.json', health)
    return failed


if __name__ == '__main__':
    sys.exit(1 if refresh() else 0)
