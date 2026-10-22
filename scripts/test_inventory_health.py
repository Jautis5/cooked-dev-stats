import copy, unittest
from inventory_health import inventory_health
from import_channel_capture import merge


class InventoryHealthTests(unittest.TestCase):
    def test_new_metrics_do_not_renew_old_inventory(self):
        a = {'id': 'instagram', 'lastSuccessAt': '2026-10-22T18:00:00Z'}
        d = {'discovery': {'instagram': {'checkedAt': '2026-10-22T18:00:00Z', 'complete': False, 'lastCompleteAt': '2026-10-22T06:00:00Z'}}}
        audit = inventory_health(d, a, '2026-10-22T18:00:00Z')
        self.assertTrue(audit['overdue'])
        self.assertEqual(audit['lastVerifiedAt'], '2026-10-22T06:00:00Z')
        self.assertEqual(audit['ageMinutes'], 720)

    def test_verified_recent_inventory_is_current(self):
        d = {'discovery': {'instagram': {'checkedAt': '2026-10-22T18:00:00Z', 'complete': True}}}
        self.assertFalse(inventory_health(d, {'id': 'instagram'}, '2026-10-22T19:00:00Z')['overdue'])
        self.assertTrue(inventory_health(d, {'id': 'instagram'}, '2026-10-22T21:00:00Z')['overdue'])

    def test_no_full_pass_is_not_a_success(self):
        self.assertEqual(inventory_health({}, {'id': 'instagram'}, '2026-10-22T18:00:00Z')['state'], 'unverified')

    def test_truncated_or_duplicate_capture_cannot_claim_complete(self):
        import datetime
        at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        data = {'channelId': 'cooked-dev', 'accounts': [{'id': 'instagram', 'url': 'https://www.instagram.com/cooked_dev/'}], 'videos': []}
        batch = {'channelId': 'cooked-dev', 'platforms': {'instagram': {'accountUrl': data['accounts'][0]['url'], 'browserProfile': 'lostastronaut.space', 'observedAt': at, 'completeList': True, 'reportedVideoCount': 20, 'posts': [{'id': 'first'}]}}}
        original = copy.deepcopy(data)
        with self.assertRaisesRegex(ValueError, 'count'): merge(data, batch)
        batch['platforms']['instagram']['posts'] *= 20
        with self.assertRaisesRegex(ValueError, 'duplicate'): merge(data, batch)
        self.assertEqual(data, original)


if __name__ == '__main__': unittest.main()
