"""Read Kit's confirmed subscriber count; publish only the aggregate, never contacts."""
import datetime
import json
import os
import pathlib
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
PATH = ROOT / 'site/data/kit.json'
API = 'https://api.kit.com/v4/'


def request(path, key):
    req = urllib.request.Request(API + path, headers={
        'X-Kit-Api-Key': key, 'Accept': 'application/json',
        'User-Agent': 'CookedDev-Stats/1.0',
    })
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)


def count_from(payload):
    count = payload.get('total_count', payload.get('pagination', {}).get('total_count'))
    if type(count) is not int or count < 0:
        raise ValueError('Missing or invalid confirmed subscriber count')
    return count


def refresh(saved, key, now, fetch=request):
    # Build an explicit public schema: never serialize API response objects.
    result = {k: saved[k] for k in (
        'version', 'channelId', 'provider', 'sourceUrl', 'definition',
        'refreshIntervalMinutes', 'totalSubscribers')}
    result['refreshIntervalMinutes'] = 15
    result['lastAttemptAt'] = now
    if not key:
        result['status'] = 'authorization_required'
        return result
    try:
        account = fetch('account', key).get('account', {})
        if ' '.join(str(account.get('name', '')).lower().split()) != 'cooked dev':
            raise ValueError('Wrong Kit account')
        # Request one record solely to obtain total_count. Discard that record in
        # memory. No email address, raw API body, or key reaches files or logs.
        payload = fetch('subscribers?status=active&include_total_count=true&per_page=1&slim=true', key)
        count = count_from(payload)
        result['totalSubscribers'] = {
            'value': count, 'at': now, 'source': 'https://app.kit.com/subscribers',
            'method': 'kit_api_v4', 'approximate': False,
        }
        result['status'] = 'ok'
    except Exception:
        # Do not print exceptions: they can contain response bodies or credentials.
        result['status'] = 'error'
    return result


def main():
    saved = json.loads(PATH.read_text())
    key = os.environ.get('KIT_API_KEY', '').strip()
    if not key and saved.get('status') == 'authorization_required':
        print('Kit auto-updates require the repository secret KIT_API_KEY.')
        return
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result = refresh(saved, key, now)
    PATH.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'provider': 'Kit', 'status': result['status']}))


if __name__ == '__main__':
    main()
