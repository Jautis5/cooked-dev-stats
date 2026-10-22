"""Inventory freshness is independent of metric refreshes and process success."""
from snapshot_merge import timestamp

MAX_AGE_SECONDS = 2 * 3600


def inventory_health(data, account, observed_at):
    report = data.get('discovery', {}).get(account['id'], {})
    verified = report.get('checkedAt') if report.get('complete') is True else report.get('lastCompleteAt')
    age = max(0, timestamp(observed_at) - timestamp(verified)) if timestamp(verified) else None
    return {
        'lastVerifiedAt': verified,
        'ageMinutes': round(age / 60, 1) if age is not None else None,
        'overdue': age is None or age > MAX_AGE_SECONDS,
        'state': 'unverified' if age is None else 'overdue' if age > MAX_AGE_SECONDS else 'current',
        'maxAgeMinutes': MAX_AGE_SECONDS // 60,
    }
