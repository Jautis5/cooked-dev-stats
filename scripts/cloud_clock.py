"""Queue the next publication check using a hosted wait timer, without an idle VM.

Each short job starts its successor through workflow_dispatch. The environment
holds that successor for 15 minutes before assigning a runner. Cron is backup.
"""
import datetime, json, os, time, urllib.error
from cloud_api import CloudAPI
from snapshot_merge import timestamp

ACTIVE = {'queued', 'in_progress', 'waiting', 'pending', 'requested'}


def collection_plan(runs, now, policy):
    ordered = sorted(runs, key=lambda r: timestamp(r.get('created_at')), reverse=True)
    active = [r for r in ordered if r.get('status') in ACTIVE]
    if active:
        if all(now-timestamp(r.get('created_at')) > policy.get('recoveryAfterMinutes',45)*60 for r in active):
            return {'action':'dispatch','cancelRunIds':[r['id'] for r in active],'reason':'Collector exceeded its recovery window.'}
        return {'action':'wait','reason':'A collector is already running or queued.'}
    latest = ordered[0] if ordered else None
    failed = latest and latest.get('conclusion') not in ['success', 'skipped']
    # The hosted wait timer already enforces the clock's interval. A separate
    # manual/cron refresh must not defer the next automatic cycle by 15 more minutes.
    cooldown = policy.get('failureRetryMinutes',3)*60 if failed else policy.get('duplicateCooldownSeconds',60)
    if latest and now-timestamp(latest.get('created_at')) < cooldown:
        return {'action':'wait','reason':'The next collection is not due yet.'}
    return {'action':'dispatch','reason':'Collection interval reached.'}


def clock_recovery_plan(runs, now, policy):
    if not policy.get('continuousClockEnabled'):
        return {'action':'disabled'}
    active = [r for r in runs if r.get('status') in ACTIVE]
    if active:
        if all(now-timestamp(r.get('created_at')) > policy.get('clockStaleMinutes',35)*60 for r in active):
            return {'action':'dispatch','cancelRunIds':[r['id'] for r in active]}
        return {'action':'wait','runIds':[r['id'] for r in active]}
    return {'action':'dispatch'}


def ensure_successor(client, current_run, sleep=time.sleep):
    """A parent ID is an idempotency key, including an uncertain dispatch response."""
    title = 'Cloud clock · after ' + str(current_run)
    def find():
        return next((r for r in client.call('/actions/workflows/clock.yml/runs?per_page=30')['workflow_runs']
                     if r.get('display_title') == title and r.get('status') in ACTIVE), None)
    child = find()
    if child:
        return child
    for attempt in range(3):
        try:
            client.call('/actions/workflows/clock.yml/dispatches',
                        {'ref':'main','inputs':{'predecessor':str(current_run),'timer':'social-stats-clock'}})
            break
        except Exception as error:
            # A failed response may still have created the successor. Allow
            # listing propagation before retrying the same parent identity.
            for _ in range(3):
                sleep(2)
                child = find()
                if child:
                    return child
            retryable = (isinstance(error, (TimeoutError, urllib.error.URLError))
                         and (not isinstance(error, urllib.error.HTTPError)
                              or error.code in (429, 500, 502, 503, 504)))
            if not retryable or attempt == 2:
                raise
            sleep(2 ** (attempt + 1))
    for _ in range(10):
        child = find()
        if child:
            return child
        sleep(2)
    raise RuntimeError('Successor was not visible after dispatch; recovery workflow must restart the clock.')


def tick(client, current_run, now=None, sleep=time.sleep):
    repository = client.call('')
    if repository.get('private') is not False:
        raise RuntimeError('Continuous collection is allowed only in this public repository; paid runners are not enabled.')
    policy = client.file('data/collection-policy.json')
    if not policy.get('continuousClockEnabled'):
        return {'action':'disabled','successor':None}
    now = now if now is not None else datetime.datetime.now(datetime.timezone.utc).timestamp()
    failure = None
    plan = {'action':'unavailable'}
    try:
        runs = client.call('/actions/workflows/refresh.yml/runs?per_page=20')['workflow_runs']
        plan = collection_plan(runs, now, policy)
        if plan['action'] == 'dispatch':
            for run_id in plan.get('cancelRunIds',[]):
                client.call('/actions/runs/'+str(run_id)+'/cancel',{})
            client.call('/actions/workflows/refresh.yml/dispatches',
                        {'ref':'main','inputs':{'reason':'continuous_clock','clock_run_id':str(current_run)}})
    except Exception as error:
        failure = error
    child = ensure_successor(client, current_run, sleep)
    result = {**plan, 'clockRunId':str(current_run),'successor':child['id'],
              'nextIntervalMinutes':policy['intervalMinutes'],'driver':'environment_wait_timer'}
    print(json.dumps(result), flush=True)
    if failure:
        raise RuntimeError('Collection dispatch failed; a successor is queued and failure recovery will check the collector.') from failure
    return result


if __name__ == '__main__':
    client=CloudAPI(os.environ['GITHUB_REPOSITORY'],os.environ['GH_TOKEN'])
    try:
        result = tick(client,os.environ['GITHUB_RUN_ID'])
    finally:
        # Completion events from token-created workflows were not delivered in
        # the live verification. Audit explicitly rather than depending on them.
        client.call('/actions/workflows/watchdog.yml/dispatches',{'ref':'main'})
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as stream:
            stream.write('## Continuous cloud publication clock\n\n'+json.dumps(result)+'\n\nThe successor waits without occupying a runner. No owner computer, Codex session, new login or paid service is used.\n')
