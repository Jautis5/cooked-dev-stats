"""Free cloud recovery. Never retries missing API access or requires the owner's PC."""
import datetime, json, os, pathlib, re, urllib.request
from snapshot_merge import timestamp
from cloud_api import CloudAPI
from cloud_clock import clock_recovery_plan
ROOT = pathlib.Path(__file__).resolve().parents[1]


def recovery_plan(runs, health, now, policy):
    cutoff = policy.get('recoveryAfterMinutes', 45) * 60
    cooldown = policy.get('retryCooldownMinutes', 15) * 60
    ordered = sorted(runs, key=lambda r: timestamp(r.get('created_at')), reverse=True)
    active = [r for r in ordered if r.get('status') in ['queued', 'in_progress', 'waiting', 'pending', 'requested']]
    if active:
        if all(now-timestamp(r.get('created_at'))>cutoff for r in active):
            return {'action':'dispatch','reason':'A cloud collector has been stuck beyond the recovery window.','cancelRunIds':[r['id'] for r in active]}
        return {'action': 'wait', 'reason': 'A cloud collector is already running or queued.', 'runId': active[0]['id']}
    if ordered and now - timestamp(ordered[0].get('created_at')) < cooldown:
        return {'action': 'wait', 'reason': 'Retry cooldown; no duplicate collection is started.'}
    latest = ordered[0] if ordered else None
    failed = latest and latest.get('status') == 'completed' and latest.get('conclusion') not in ['success', 'skipped']
    age = now - timestamp(health.get('completedAt'))
    if not failed and 0 <= age <= cutoff and health.get('provider') == 'GitHub Actions' and health.get('status') == 'completed':
        return {'action': 'healthy', 'reason': 'Cloud collection is recent. Unavailable platform access is not a scheduler failure.'}
    return {'action': 'dispatch', 'reason': 'Latest collector failed.' if failed else 'No recent successful cloud collection was saved.'}


def api(repository, token, path, body=None):
    return CloudAPI(repository, token).call(path, body)


def run():
    repository = os.environ['GITHUB_REPOSITORY']
    token = os.environ['GH_TOKEN']  # Ephemeral Actions token; never logged, persisted or sent elsewhere.
    policy = json.loads((ROOT / 'data/collection-policy.json').read_text())
    path = ROOT / 'data/health.json'
    health = json.loads(path.read_text()) if path.exists() else {}
    runs = api(repository, token, '/actions/workflows/refresh.yml/runs?per_page=20')['workflow_runs']
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    if policy.get('continuousClockEnabled'):
        if api(repository,token,'').get('private') is not False:
            raise RuntimeError('Automatic clock is restricted to the free public repository.')
        clocks = api(repository,token,'/actions/workflows/clock.yml/runs?per_page=30')['workflow_runs']
        clock_plan = clock_recovery_plan(clocks,now,policy)
        if clock_plan['action']=='dispatch':
            for run_id in clock_plan.get('cancelRunIds',[]):
                api(repository,token,'/actions/runs/'+str(run_id)+'/cancel',{})
            api(repository,token,'/actions/workflows/clock.yml/dispatches',{'ref':'main'})
        print(json.dumps({'clockRecovery':clock_plan}))
    plan = recovery_plan(runs, health, now, policy)
    if plan['action'] == 'dispatch':
        for run_id in plan.get('cancelRunIds', []):
            api(repository, token, '/actions/runs/'+str(run_id)+'/cancel', {})
        api(repository, token, '/actions/workflows/refresh.yml/dispatches', {'ref': 'main','inputs':{'reason':'watchdog'}})
        plan['dispatched'] = True
    else:
        plan['dispatched'] = False
    print(json.dumps(plan))
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as stream:
            stream.write('## Social Stats cloud watchdog\n\n' + plan['reason'] + '\n\nRecovery requested: ' + str(plan['dispatched']) + '. No browser, Codex session, account login or owner computer is used.\n')
    return plan


if __name__ == '__main__':
    run()
