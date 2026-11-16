import copy
import json
import unittest
from collect_kit import PATH, refresh, count_from


class KitTests(unittest.TestCase):
    def setUp(self):
        self.saved = json.loads(PATH.read_text())
        self.now = '2026-11-16T15:00:00Z'

    def test_confirmed_count_and_private_fields_are_discarded(self):
        calls = []
        def fetch(path, key):
            calls.append(path)
            return {'account': {'name': 'Cooked Dev'}} if path == 'account' else {
                'total_count': 1741, 'subscribers': [{'email_address': 'private@example.com'}]}
        result = refresh(self.saved, 'test-key', self.now, fetch)
        self.assertEqual(result['totalSubscribers']['value'], 1741)
        self.assertEqual(result['status'], 'ok')
        self.assertIn('status=active', calls[1])
        self.assertNotIn('private@example.com', json.dumps(result))
        self.assertNotIn('test-key', json.dumps(result))

    def test_failure_missing_count_wrong_account_keep_actual_observation(self):
        for payload in ({}, {'total_count': None}, {'total_count': -1}, {'total_count': True}):
            def fetch(path, key):
                return {'account': {'name': 'Cooked Dev'}} if path == 'account' else payload
            result = refresh(self.saved, 'test-key', self.now, fetch)
            self.assertEqual(result['totalSubscribers'], self.saved['totalSubscribers'])
            self.assertEqual(result['status'], 'error')
        result = refresh(self.saved, 'test-key', self.now, lambda *args: {'account': {'name': 'Other brand'}})
        self.assertEqual(result['status'], 'error')

    def test_zero_and_decreases_are_real_counts(self):
        for value in (0, 1700):
            def fetch(path, key):
                return {'account': {'name': 'Cooked Dev'}} if path == 'account' else {'pagination': {'total_count': value}}
            result = refresh(self.saved, 'test-key', self.now, fetch)
            self.assertEqual(result['totalSubscribers']['value'], value)
            self.assertEqual(result['status'], 'ok')

    def test_missing_key_does_not_fetch_or_advance_observation(self):
        before = copy.deepcopy(self.saved)
        result = refresh(self.saved, '', self.now, lambda *args: self.fail('No API call without a key'))
        self.assertEqual(result['status'], 'authorization_required')
        self.assertEqual(result['totalSubscribers'], before['totalSubscribers'])
        self.assertEqual(self.saved, before)


if __name__ == '__main__':
    unittest.main()
