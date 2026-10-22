import copy
import json
import unittest
from unittest.mock import patch

import collect as base
import public_x
from public_fallbacks import add_post


def status(identity='123', handle='right'):
    return {'type': 'status', 'id': identity, 'text': 'Video',
            'author': {'id': '456', 'screen_name': handle, 'protected': False},
            'created_timestamp': 1792594934, 'media': {'all': [{'type': 'video'}]},
            'reposted_by': None, 'views': 6, 'likes': 0, 'replies': 2, 'reposts': 1}


class PublicXTests(unittest.TestCase):
    def test_exact_owner_and_public_video_required(self):
        good = status()
        self.assertTrue(public_x.owned_video(good, 'RIGHT', '123'))
        for key, value in [('id', '999'), ('reposted_by', {'screen_name': 'right'}),
                           ('media', {'all': [], 'quote': {'type': 'video'}}), ('type', 'tombstone')]:
            wrong = copy.deepcopy(good)
            wrong[key] = value
            self.assertFalse(public_x.owned_video(wrong, 'right', '123'))
        for author in [{'screen_name': 'wrong', 'protected': False}, {'screen_name': 'right', 'protected': True}]:
            wrong = dict(good, author=author)
            self.assertFalse(public_x.owned_video(wrong, 'right', '123'))

    def test_known_post_keeps_provenance_and_real_zero(self):
        post = {'id': '123', 'url': 'https://x.com/right/status/123', 'metrics': {}}
        with patch.object(base, 'request', return_value=json.dumps({'code': 200, 'status': status()})):
            public_x.known_post(post, {'handle': 'right'})
        self.assertEqual(post['metrics']['views']['value'], 6)
        self.assertEqual(post['metrics']['likes']['value'], 0)
        self.assertEqual(post['metrics']['shares']['value'], 1)
        self.assertEqual(post['metrics']['views']['source'], post['url'])
        self.assertEqual(post['metrics']['views']['via'], public_x.API + 'status/123')
        self.assertIsNone(post['metrics']['views']['upstreamObservedAt'])

    def test_null_and_non_integer_counts_never_erase_last_values(self):
        original = {'value': 17, 'at': '2026-10-20T00:00:00Z'}
        post = {'url': 'https://x.com/right/status/123', 'metrics': {'views': original}}
        for value in [None, True, -1, '10K', 12.4]:
            public_x.observe(post, 'views', value, 'status/123')
            self.assertEqual(post['metrics']['views'], original)

    def test_numeric_profile_route_and_bounded_inventory(self):
        data = {'tracking': {'startedAt': '2026-10-20T00:00:00Z'}, 'videos': []}
        account = {'handle': 'right', 'url': 'https://x.com/right', 'metrics': {}}
        profile = {'code': 200, 'user': {'id': '456', 'screen_name': 'right', 'protected': False, 'followers': 0}}
        page = {'code': 200, 'results': [status(), status('999', 'wrong')], 'cursor': {'bottom': 'end'}}
        with patch.object(base, 'request', side_effect=[json.dumps(profile), json.dumps(page), ValueError('not found')]) as request:
            report = public_x.discover(data, account, add_post)
        self.assertIn('profile/id:456/media', request.call_args_list[1].args[0])
        self.assertEqual(report['listedPosts'], 1)
        self.assertFalse(report['complete'])
        self.assertEqual(len(data['videos']), 1)
        self.assertEqual(account['metrics']['followers']['value'], 0)

    def test_errors_are_not_empty_inventories(self):
        data = {'videos': []}
        account = {'handle': 'right', 'url': 'https://x.com/right'}
        with patch.object(base, 'request', return_value=json.dumps({'code': 404, 'results': []})):
            with self.assertRaises(ValueError): public_x.discover(data, account, add_post)
        self.assertEqual(data['videos'], [])

    def test_failed_handle_lookup_recovers_id_from_verified_known_video(self):
        post = {'id': '123', 'url': 'https://x.com/right/status/123', 'metrics': {}}
        data = {'videos': [{'id': 'v', 'number': 1, 'posts': {'x': post}}]}
        page = {'code': 200, 'results': [status()], 'cursor': {}}
        with patch.object(base, 'request', side_effect=[ValueError('404'),
                          json.dumps({'code': 200, 'status': status()}), json.dumps(page)]) as request:
            report = public_x.discover(data, {'handle': 'right', 'url': 'https://x.com/right'}, add_post)
        self.assertIn('profile/id:456/media', request.call_args_list[2].args[0])
        self.assertEqual(report['listedPosts'], 1)
        self.assertEqual(post['metrics']['views']['value'], 6)

    def test_tracking_cutoff_and_excluded_ids_still_apply(self):
        data = {'tracking': {'startedAt': '2026-10-22T00:00:00Z'}, 'videos': []}
        account = {'handle': 'right', 'url': 'https://x.com/right'}
        profile = {'code': 200, 'user': {'id': '456', 'screen_name': 'right', 'protected': False}}
        page = {'code': 200, 'results': [status()], 'cursor': {}}
        with patch.object(base, 'request', side_effect=[json.dumps(profile), json.dumps(page)]):
            public_x.discover(data, account, add_post)
        self.assertEqual(data['videos'], [])


if __name__ == '__main__':
    unittest.main()
