import json
import unittest

from collect_lumo_kit import refresh

NOW = '2026-11-24T14:00:00+00:00'
ACCOUNT = {'account': {'name': 'LUMO', 'timezone': {'name': 'Europe/Vilnius'}}}
WINDOW = {'starting': '2026-11-18T00:00:00+02:00', 'ending': '2026-11-24T23:59:59+02:00'}


def fixtures(path, key):
    if path == 'account':
        return ACCOUNT
    if path.startswith('subscribers?'):
        return {'pagination': {'total_count': 294}, 'subscribers': [{'email_address': 'contact@example.test'}]}
    if path.startswith('account/growth_stats?'):
        start, end = (param.split('=', 1)[1] for param in path.split('?')[1].split('&'))
        return {'stats': {'starting': start, 'ending': end, 'new_subscribers': 12,
                          'cancellations': 15, 'net_new_subscribers': -3}}
    if path == 'account/email_stats':
        return {'stats': {**WINDOW, 'sent': 100, 'opened': 80, 'clicked': 20, 'open_rate': 80,
                          'click_rate': 20, 'open_tracking_enabled': False, 'click_tracking_enabled': True,
                          'unsubscribe_rate': 2, 'bounce_rate': 1}}
    if path.startswith('forms?'):
        if 'status=archived' in path:
            return {'forms': [], 'pagination': {'has_next_page': False}}
        return {
            'forms': [{'type': 'hosted', 'id': 9, 'subscriber_count': 230, 'name': 'private@example.test'}]
            if 'after=' not in path else [{'type': 'embed', 'id': 12}],
            'pagination': {'has_next_page': 'after=' not in path, 'end_cursor': 'abc='},
        }
    if path.startswith('forms/12/subscribers?'):
        return {'pagination': {'total_count': 22}}
    if path.startswith('broadcasts/stats?'):
        return {
            'broadcasts': [
                {'id': 11, 'send_at': NOW, 'subject': 'Private subject',
                 'stats': {'status': 'completed', 'recipients': 294, 'open_tracking_disabled': False,
                           'emails_opened': 100, 'open_rate': 34, 'click_tracking_disabled': True,
                           'unsubscribes': 3, 'unsubscribe_rate': 1.02}},
                {'id': 12, 'send_at': None, 'stats': {'status': 'draft'}},
            ],
            'pagination': {'has_next_page': False},
        }
    raise AssertionError(path)


class LumoKitTests(unittest.TestCase):
    def test_collects_only_approved_aggregates_and_keeps_zero_distinct_from_unknown(self):
        result = refresh({}, 'secret-key', NOW, fixtures)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['totalSubscribers']['value'], 294)
        self.assertEqual(result['growth']['value']['7']['net_new_subscribers'], -3)
        self.assertEqual(result['growth']['value']['7']['starting'], '2026-11-18')
        self.assertIsNone(result['email']['value']['open_rate'])
        self.assertEqual(result['email']['value']['click_rate'], 20)
        self.assertEqual([form['subscribers'] for form in result['forms']['value']], [230, 22])
        self.assertEqual([row['id'] for row in result['broadcasts']['value']], [11])
        self.assertIsNone(result['broadcasts']['value'][0]['clickRate'])
        for private in ('@example.test', 'Private subject', 'secret-key'):
            self.assertNotIn(private, json.dumps(result))

    def test_blocks_wrong_account_before_any_reporting_request(self):
        requests = []
        def wrong_account(path, key):
            requests.append(path)
            return {'account': {'name': 'Cooked Dev'}}
        self.assertEqual(refresh({}, 'wrong', NOW, wrong_account)['status'], 'error')
        self.assertEqual(requests, ['account'])

    def test_partial_failure_preserves_only_failed_sections(self):
        previous = {'email': {'at': '2026-11-23T14:00:00+00:00', 'value': {'sent': 22}}}
        def no_email(path, key):
            if path == 'account/email_stats':
                raise OSError('Temporarily unavailable')
            if path.startswith('subscribers?'):
                return {'total_count': 0}
            return fixtures(path, key)
        result = refresh(previous, 'secret-key', NOW, no_email)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['errors'], ['email'])
        self.assertEqual(result['email'], previous['email'])
        self.assertEqual(result['totalSubscribers'], {'at': NOW, 'value': 0})


if __name__ == '__main__':
    unittest.main()
