import copy
import json
import unittest
from unittest.mock import patch

import collect as base
from youtube_inventory import discover
from public_fallbacks import refresh_fallbacks

CHANNEL = 'UCNPkHyLJotjamsFxts47T2A'
FIRST, SECOND = 'abcdefghijk', 'lmnopqrstuv'


def short(identity):
    return {'richItemRenderer': {'content': {'shortsLockupViewModel': {
        'onTap': {'innertubeCommand': {'reelWatchEndpoint': {'videoId': identity},
                    'commandMetadata': {'webCommandMetadata': {'url': '/shorts/' + identity}}}},
        'overlayMetadata': {'primaryText': {'content': 'Identical caption'}}}}}}


def more(value):
    return {'continuationItemRenderer': {'continuationEndpoint': {'continuationCommand': {'token': value}}}}


def profile(items, owner=CHANNEL, tabs=None):
    tabs = tabs or [{'tabRenderer': {'selected': True, 'title': 'Shorts',
        'endpoint': {'browseEndpoint': {'browseId': owner}, 'commandMetadata': {'webCommandMetadata': {'url': '/@owner/shorts'}}},
        'content': {'richGridRenderer': {'contents': items}}}}]
    return {'metadata': {'channelMetadataRenderer': {'externalId': owner}},
            'contents': {'twoColumnBrowseResultsRenderer': {'tabs': tabs}}}


def page(value):
    return 'ytcfg.set({"INNERTUBE_CLIENT_VERSION":"2.20261105.00.00"});var ytInitialData = ' + json.dumps(value) + ';'


def continued(items):
    return {'onResponseReceivedActions': [{'appendContinuationItemsAction': {'continuationItems': items}}]}


def player(identity, owner=CHANNEL, status='OK', date='2026-11-05T09:00:00Z'):
    return 'var ytInitialPlayerResponse = ' + json.dumps({'videoDetails': {'videoId': identity,
        'channelId': owner, 'isPrivate': False, 'title': 'Identical caption'},
        'playabilityStatus': {'status': status}, 'microformat': {'playerMicroformatRenderer': {'publishDate': date}}}) + ';'


class YoutubeInventoryTests(unittest.TestCase):
    def fixture(self):
        account = {'id': 'youtube', 'name': 'YouTube', 'expectedChannelId': CHANNEL,
                   'url': 'https://www.youtube.com/channel/' + CHANNEL, 'status': 'partial'}
        metric = {'value': 123, 'at': '2026-11-01T00:00:00Z', 'source': 'https://www.youtube.com/shorts/' + FIRST}
        data = {'accounts': [account], 'videos': [{'id': 'known', 'number': 4, 'assetUrl': 'https://drive.google.com/file/d/original/view',
                 'posts': {'youtube': {'id': FIRST, 'url': metric['source'], 'metrics': {'views': metric}}}}]}
        return data, account

    def test_follows_next_page_and_discovers_real_new_id_without_caption_merge(self):
        data, account = self.fixture(); before = copy.deepcopy(data['videos'][0])
        def request(url):
            return player(SECOND) if '/watch?' in url else page(profile([short(FIRST), more('page-two')]))
        calls = []
        def following(cursor, version):
            calls.append((cursor, version)); return continued([short(SECOND)])
        result = discover(data, account, request, following)
        self.assertTrue(result['complete']); self.assertEqual(result['pages'], 2)
        self.assertEqual(result['listedPosts'], 2); self.assertEqual(result['newVideos'], 1)
        self.assertEqual(calls, [('page-two', '2.20261105.00.00')])
        self.assertEqual(data['videos'][0], before); self.assertEqual(data['videos'][1]['number'], 5)
        self.assertEqual(data['videos'][1]['posts']['youtube']['id'], SECOND)
        self.assertEqual(data['videos'][1]['posts']['youtube']['metrics'], {})
        self.assertIsNone(data['videos'][1]['assetUrl'])

    def test_cursor_loop_does_not_claim_complete_or_refresh_metrics(self):
        data, account = self.fixture(); original = copy.deepcopy(data)
        result = discover(data, account, lambda _: page(profile([short(FIRST), more('same')])), lambda *_: continued([short(FIRST), more('same')]))
        self.assertFalse(result['complete']); self.assertNotIn('lastCompleteAt', result)
        self.assertEqual(data, original)

    def test_page_limit_is_partial(self):
        data, account = self.fixture()
        result = discover(data, account, lambda _: page(profile([short(FIRST), more('next')])), max_pages=1)
        self.assertFalse(result['complete']); self.assertNotIn('lastCompleteAt', result)

    def test_failed_next_page_retains_verified_first_page_and_old_marker(self):
        data, account = self.fixture(); old = '2026-10-20T00:00:00Z'
        data['discovery'] = {'youtube': {'lastCompleteAt': old}}
        def fail(*_): raise ValueError('Unavailable')
        with patch.object(base, 'request', return_value=page(profile([short(FIRST), more('next')]))), patch('youtube_inventory.browse', side_effect=fail):
            refresh_fallbacks(data)
        self.assertFalse(data['discovery']['youtube']['complete'])
        self.assertEqual(data['discovery']['youtube']['lastCompleteAt'], old)

    def test_unknown_grid_is_partial_not_empty(self):
        data, account = self.fixture()
        result = discover(data, account, lambda _: page(profile([{'newUnsupportedRenderer': {}}])))
        self.assertFalse(result['complete']); self.assertNotIn('lastCompleteAt', result)

    def test_owner_mismatch_rejected_before_mutation(self):
        data, account = self.fixture(); original = copy.deepcopy(data)
        with self.assertRaisesRegex(ValueError, 'owner'):
            discover(data, account, lambda _: page(profile([], 'UCgHxdk2zTRXwsoCrICSwiRg')))
        self.assertEqual(data, original)

    def test_foreign_or_nonpublic_new_video_is_not_adopted(self):
        for owner, status in [('UCgHxdk2zTRXwsoCrICSwiRg', 'OK'), (CHANNEL, 'LOGIN_REQUIRED')]:
            data, account = self.fixture()
            result = discover(data, account, lambda url: player(SECOND, owner, status) if '/watch?' in url else page(profile([short(SECOND)])))
            self.assertFalse(result['complete']); self.assertEqual(len(data['videos']), 1)

    def test_date_only_does_not_bypass_legacy_cutoff(self):
        data, account = self.fixture(); data['tracking'] = {'startedAt': '2026-10-20T00:00:00Z'}
        result = discover(data, account, lambda url: player(SECOND, date='2026-11-05') if '/watch?' in url else page(profile([short(SECOND)])))
        self.assertFalse(result['complete']); self.assertEqual(len(data['videos']), 1)

    def test_empty_channel_requires_an_explicit_owned_empty_state(self):
        data, account = self.fixture(); empty = profile([], tabs=[{'tabRenderer': {'title': 'Home', 'content': {'messageRenderer': {'text': {'simpleText': "This channel doesn't have any content"}}}}}])
        result = discover(data, account, lambda _: page(empty)); self.assertTrue(result['complete'])
        self.assertEqual(result['listedPosts'], 0); self.assertEqual(len(data['videos']), 1)
        empty['contents']['twoColumnBrowseResultsRenderer']['tabs'][0]['tabRenderer']['content'] = {}
        with self.assertRaisesRegex(ValueError, 'authoritative'): discover(data, account, lambda _: page(empty))

    def test_full_marker_retains_actual_completion_time_through_fallback_wrapper(self):
        data, account = self.fixture(); at = '2026-11-05T12:00:00Z'
        with patch('youtube_inventory.stamp', return_value=at), patch.object(base, 'request', return_value=page(profile([short(FIRST)]))):
            refresh_fallbacks(data)
        report = data['discovery']['youtube']
        self.assertTrue(report['complete']); self.assertEqual(report['lastCompleteAt'], at)
        self.assertEqual(report['checkedAt'], at)

    def test_scheduled_entries_and_recommendation_shelves_are_not_public_videos(self):
        data, account = self.fixture()
        scheduled = {'richItemRenderer': {'content': {'videoRenderer': {'videoId': SECOND, 'upcomingEventData': {'startTime': '9999999999'}}}}}
        result = discover(data, account, lambda _: page(profile([short(FIRST), scheduled, {'richSectionRenderer': {'contents': [short(SECOND)]}}])))
        self.assertFalse(result['complete']); self.assertEqual(result['listedPosts'], 1)
        self.assertEqual(len(data['videos']), 1)

    def test_future_publication_metadata_is_not_imported_as_public(self):
        data, account = self.fixture()
        result = discover(data, account, lambda url: player(SECOND, date='2050-01-01T00:00:00Z') if '/watch?' in url else page(profile([short(SECOND)])))
        self.assertFalse(result['complete']); self.assertEqual(len(data['videos']), 1)

    def test_empty_initial_grid_is_unknown_not_confirmed_empty(self):
        data, account = self.fixture()
        result = discover(data, account, lambda _: page(profile([])))
        self.assertFalse(result['complete']); self.assertNotIn('lastCompleteAt', result)

    def test_all_advertised_video_tabs_must_be_checked(self):
        data, account = self.fixture()
        root = profile([short(FIRST)])
        root['contents']['twoColumnBrowseResultsRenderer']['tabs'].append({'tabRenderer': {'selected': False, 'title': 'Videos',
            'endpoint': {'browseEndpoint': {'browseId': CHANNEL}, 'commandMetadata': {'webCommandMetadata': {'url': '/@owner/videos'}}}}})
        result = discover(data, account, lambda _: page(root))
        self.assertFalse(result['complete'])
        self.assertEqual(result['tabsChecked'], ['shorts', 'videos'])


if __name__ == '__main__': unittest.main()
