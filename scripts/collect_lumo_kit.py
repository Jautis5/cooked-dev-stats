"""Collect aggregate newsletter analytics for the LUMO Kit account."""

import datetime as dt
import json
import math
import os
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from collect_kit import ROOT, count_from, request

PATH = ROOT / 'site/data/lumo-kit.json'
COUNT_QUERY = 'status=active&include_total_count=true&per_page=1&slim=true'
GROWTH_COUNTS = ('new_subscribers', 'cancellations')
EMAIL_COUNTS = ('sent', 'opened', 'clicked')
EMAIL_RATES = ('open_rate', 'click_rate', 'unsubscribe_rate', 'bounce_rate')


def count(value, *, signed=False):
    if type(value) is not int or (not signed and value < 0):
        raise ValueError('Invalid Kit count')
    return value


def rate(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100:
        return None
    return value


def timestamp(value):
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError('Missing Kit time zone')
    return parsed.isoformat()


def paginated(fetch, path, field, **params):
    cursors = set()
    while True:
        page = fetch(f'{path}?{urlencode(params)}')
        if not isinstance(page[field], list):
            raise ValueError('Invalid Kit page')
        yield from page[field]
        pagination = page['pagination']
        if not pagination['has_next_page']:
            return
        cursor = pagination['end_cursor']
        if not isinstance(cursor, str) or not cursor or cursor in cursors:
            raise ValueError('Invalid Kit cursor')
        cursors.add(cursor)
        params['after'] = cursor


def growth(fetch, today):
    windows = {}
    for days in (7, 30, 90):
        start = today - dt.timedelta(days=days - 1)
        stats = fetch(f'account/growth_stats?starting={start}&ending={today}')['stats']
        windows[str(days)] = {
            **{field: count(stats[field]) for field in GROWTH_COUNTS},
            'net_new_subscribers': count(stats['net_new_subscribers'], signed=True),
            'starting': timestamp(stats['starting']),
            'ending': timestamp(stats['ending']),
        }
    return windows


def email(fetch):
    stats = fetch('account/email_stats')['stats']
    open_tracking = stats.get('open_tracking_enabled') is True
    click_tracking = stats.get('click_tracking_enabled') is True
    data = {
        **{field: count(stats[field]) for field in EMAIL_COUNTS},
        **{field: rate(stats.get(field)) for field in EMAIL_RATES},
        'starting': timestamp(stats['starting']),
        'ending': timestamp(stats['ending']),
    }
    if not open_tracking:
        data.update(opened=None, open_rate=None)
    if not click_tracking:
        data.update(clicked=None, click_rate=None)
    return data


def forms(fetch):
    sources = []
    for status in ('active', 'archived'):
        for form in paginated(fetch, 'forms', 'forms', status=status, include='subscriber_count'):
            form_id = count(form['id'])
            confirmed = form.get('subscriber_count')
            if confirmed is None:
                confirmed = count_from(fetch(f'forms/{form_id}/subscribers?{COUNT_QUERY}'))
            sources.append({
                'id': form_id,
                'type': 'landing_page' if form.get('type') == 'hosted' else 'form',
                'subscribers': count(confirmed),
                'archived': status == 'archived',
            })
    return sorted(sources, key=lambda form: (-form['subscribers'], form['id']))


def broadcasts(fetch):
    result = []
    for row in paginated(fetch, 'broadcasts/stats', 'broadcasts', status='completed'):
        stats = row['stats']
        if stats['status'] != 'completed' or not row.get('send_at'):
            continue
        open_tracking = stats.get('open_tracking_disabled') is False
        click_tracking = stats.get('click_tracking_disabled') is False
        result.append({
            'id': count(row['id']),
            'sentAt': timestamp(row['send_at']),
            'recipients': count(stats['recipients']),
            'opens': count(stats['emails_opened']) if open_tracking else None,
            'openRate': rate(stats.get('open_rate')) if open_tracking else None,
            'clickRate': rate(stats.get('click_rate')) if click_tracking else None,
            'clicks': count(stats['total_clicks']) if click_tracking and stats.get('show_total_clicks') is True else None,
            'unsubscribes': count(stats['unsubscribes']),
            'unsubscribeRate': rate(stats.get('unsubscribe_rate')),
        })
    return sorted(result, key=lambda row: dt.datetime.fromisoformat(row['sentAt']), reverse=True)


def refresh(saved, key, now, fetch=request):
    result = {
        'version': 1, 'channelId': 'lumo-wins', 'lastAttemptAt': now,
        **{field: saved[field] for field in ('totalSubscribers', 'growth', 'email', 'forms', 'broadcasts') if field in saved},
    }

    def read(path):
        return fetch(path, key)

    try:
        account = read('account')['account']
        if ' '.join(account['name'].casefold().split()) != 'lumo':
            raise ValueError('Wrong Kit account')
        today = dt.datetime.fromisoformat(now).astimezone(ZoneInfo(account['timezone']['name'])).date()
    except Exception:
        result['status'] = 'error'
        return result

    collectors = {
        'totalSubscribers': lambda: count_from(read('subscribers?' + COUNT_QUERY)),
        'growth': lambda: growth(read, today),
        'email': lambda: email(read),
        'forms': lambda: forms(read),
        'broadcasts': lambda: broadcasts(read),
    }
    errors = []
    for field, collect in collectors.items():
        try:
            result[field] = {'at': now, 'value': collect()}
        except Exception:
            # Keep the previous observation and log only the section name.
            errors.append(field)
    result['errors'] = errors
    result['status'] = 'ok' if not errors else 'error' if len(errors) == len(collectors) else 'partial'
    return result


def main():
    key = os.environ.get('LUMO_KIT_PUBLIC_API_KEY', '').strip()
    if not key:
        print('LUMO Kit public collection is not configured.')
        return
    saved = json.loads(PATH.read_text())
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    result = refresh(saved, key, now)
    PATH.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'unavailableSections': result.get('errors', [])}))


if __name__ == '__main__':
    main()
