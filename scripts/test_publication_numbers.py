"""Verified ledger numbers remain reserved in sparse browser snapshots."""
import copy
import json
import pathlib
import unittest

from publications import reconcile

ROOT = pathlib.Path(__file__).resolve().parents[1]


class PublicationNumberTests(unittest.TestCase):
    def setUp(self):
        self.ledger = json.loads((ROOT / 'data/publications.json').read_text())
        self.feed = json.loads((ROOT / 'data/latest.json').read_text())
        self.groups = [g for g in self.ledger['groups'] if g['channelId'] == 'cooked-dev']

    def sparse(self, videos=None):
        return {'version': 1, 'accounts': copy.deepcopy(self.feed['accounts']),
                'videos': copy.deepcopy(videos or []), 'history': []}

    def assert_explicit_numbers(self, data):
        by_id = {v['id']: v for v in data['videos']}
        for group in self.groups:
            if group.get('number'):
                self.assertEqual(by_id[group['videoId']]['number'], group['number'])
        self.assertEqual(len(data['videos']), len({v['number'] for v in data['videos']}))

    def test_real_ledger_can_reconcile_an_empty_browser_snapshot(self):
        data = reconcile(self.sparse(), self.ledger)
        self.assert_explicit_numbers(data)
        self.assertEqual({g['videoId'] for g in self.groups}, {v['id'] for v in data['videos']})

    def test_partial_snapshot_preserves_existing_post_metrics_and_high_number(self):
        known = copy.deepcopy(self.feed['videos'][0])
        unknown = {'id': 'unmatched-publication', 'number': 1000, 'posts': {}}
        data = reconcile(self.sparse([known, unknown]), self.ledger)
        self.assert_explicit_numbers(data)
        original_posts = {(p, str(post['id'])): post.get('metrics', {}) for p, post in known['posts'].items()}
        current_posts = {(p, str(post['id'])): post.get('metrics', {}) for v in data['videos'] for p, post in v['posts'].items()}
        self.assertTrue(original_posts.items() <= current_posts.items())
        self.assertEqual(next(v for v in data['videos'] if v['id'] == unknown['id']), unknown)
        allocated = [v for v in data['videos'] if v['id'] != known['id'] and v['id'] != unknown['id']
                     and any(g['videoId'] == v['id'] and not g.get('number') for g in self.groups)]
        self.assertTrue(all(v['number'] > 1000 for v in allocated))

    def test_explicit_targets_keep_numbers_when_ledger_order_changes(self):
        for groups in [list(reversed(self.ledger['groups'])), self.ledger['groups'][7:] + self.ledger['groups'][:7]]:
            self.assert_explicit_numbers(reconcile(self.sparse(), {'groups': groups}))

    def test_other_channel_numbers_do_not_change_cooked_allocation(self):
        plain = reconcile(self.sparse(), self.ledger)
        foreign = copy.deepcopy(self.ledger)
        foreign['groups'].append({'id': 'foreign-number-reservation', 'channelId': 'another-channel', 'number': 99999})
        self.assertEqual(plain, reconcile(self.sparse(), foreign))

    def test_conflicting_explicit_numbers_still_fail(self):
        ledger = copy.deepcopy(self.ledger)
        numbered = [g for g in ledger['groups'] if g['channelId'] == 'cooked-dev' and g.get('number')]
        numbered[-1]['number'] = numbered[0]['number']
        with self.assertRaisesRegex(ValueError, 'Conflicting canonical video numbers'):
            reconcile(self.sparse(), ledger)

    def assert_full_feed_replay(self, feed):
        first = reconcile(copy.deepcopy(feed), self.ledger)
        self.assertEqual(first, reconcile(copy.deepcopy(first), self.ledger))
        self.assert_explicit_numbers(first)
        explicit_targets = {g['videoId'] for g in self.groups if g.get('number')}
        survivors = {v['id']: v for v in first['videos']}
        for old in feed['videos']:
            if old['id'] in survivors and old['id'] not in explicit_targets:
                self.assertEqual(survivors[old['id']]['number'], old['number'])
        before = {(p, str(post['id'])): post.get('metrics', {}) for v in feed['videos'] for p, post in v['posts'].items()}
        after = {(p, str(post['id'])): post.get('metrics', {}) for v in first['videos'] for p, post in v['posts'].items()}
        self.assertTrue(before.items() <= after.items())
        return first

    def test_replaying_the_real_full_feed_preserves_publications_and_metrics(self):
        self.assert_full_feed_replay(self.feed)

    def test_new_verified_association_does_not_require_premerged_feed(self):
        feed = reconcile(copy.deepcopy(self.feed), self.ledger)
        group = next(g for g in self.groups if g.get('number') and 'youtube' in g['posts'])
        target = next(v for v in feed['videos'] if v['id'] == group['videoId'])
        post = target['posts'].pop('youtube')
        orphan_id = 'unmerged-youtube-' + post['id']
        feed['videos'].append({'id': orphan_id, 'number': max(v['number'] for v in feed['videos']) + 1,
                               'posts': {'youtube': post}})
        merged = self.assert_full_feed_replay(feed)
        self.assertFalse(any(v['id'] == orphan_id for v in merged['videos']))
        self.assertEqual(next(v for v in merged['videos'] if v['id'] == group['videoId'])['posts']['youtube'], post)


if __name__ == '__main__':
    unittest.main()
