import copy
import datetime
import unittest
from unittest.mock import patch

import official_broker
from refresh_all import metric_health


def fixture():
    at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    data = {'version': 1, 'channelId': 'indian-builds', 'tracking': {'startedAt': '2026-10-20T00:00:00Z'},
            'accounts': [{'id': 'tiktok', 'name': 'TikTok', 'expectedHandle': 'indian_builds', 'url': 'https://www.tiktok.com/@indian_builds', 'metrics': {}, 'status': 'partial'}], 'videos': []}
    observation = {'version': 1, 'channelId': 'indian-builds', 'platform': 'tiktok', 'owner': {'handle': 'indian_builds'}, 'checkedAt': at,
        'inventory': {'complete': True, 'scope': 'since_tracking_start'}, 'accountMetrics': {'followers': {'value': 0, 'apiMetric': 'follower_count'}},
        'posts': [{'id': '123', 'url': 'https://www.tiktok.com/@indian_builds/video/123', 'title': 'New video', 'publishedAt': '2026-10-21T12:00:00Z', 'metrics': {'views': {'value': 0, 'apiMetric': 'view_count'}}}]}
    return data, observation


class OfficialBrokerTests(unittest.TestCase):
    def test_real_zero_exact_identity_and_retrieval_time(self):
        data, observation = fixture()
        official_broker.apply(data, 'tiktok', observation)
        metric = data['videos'][0]['posts']['tiktok']['metrics']['views']
        self.assertEqual(metric['value'], 0)
        self.assertEqual(metric['at'], observation['checkedAt'])
        self.assertEqual(metric['method'], 'official_api')
        self.assertTrue(data['discovery']['tiktok']['complete'])
        report = metric_health(data, observation['checkedAt'])['tiktok']
        self.assertEqual(report['viewsUpdated'], 1)
        self.assertEqual(report['access'], 'authorized_cloud')

    def test_wrong_owner_rejected_transactionally(self):
        for mutation in ['channelId', 'owner', 'url']:
            data, observation = fixture()
            if mutation == 'channelId': observation['channelId'] = 'cooked-dev'
            elif mutation == 'owner': observation['owner']['handle'] = 'wrong'
            else: observation['posts'][0]['url'] = 'https://www.tiktok.com/@wrong/video/123'
            original = copy.deepcopy(data)
            with self.assertRaises(ValueError): official_broker.apply(data, 'tiktok', observation)
            self.assertEqual(data, original)

    def test_exclusions_and_old_content_are_not_imported(self):
        data, observation = fixture()
        data['tracking']['excludedPostIds'] = {'tiktok': ['123']}
        official_broker.apply(data, 'tiktok', observation)
        self.assertEqual(data['videos'], [])
        data, observation = fixture()
        observation['posts'][0]['publishedAt'] = '2025-01-01T00:00:00Z'
        official_broker.apply(data, 'tiktok', observation)
        self.assertEqual(data['videos'], [])

    def test_null_does_not_overwrite_known_count_or_change_its_time(self):
        data, observation = fixture()
        official_broker.apply(data, 'tiktok', observation)
        original = copy.deepcopy(data['videos'][0]['posts']['tiktok']['metrics']['views'])
        observation['posts'][0]['metrics']['views']['value'] = None
        official_broker.apply(data, 'tiktok', observation)
        self.assertEqual(data['videos'][0]['posts']['tiktok']['metrics']['views'], original)

    def test_metric_response_dates_and_inventory_end_are_separate(self):
        data, observation = fixture()
        now = datetime.datetime.now(datetime.timezone.utc)
        batch = (now - datetime.timedelta(seconds=30)).isoformat()
        measured = (now - datetime.timedelta(seconds=10)).isoformat()
        ended = (now - datetime.timedelta(seconds=1)).isoformat()
        observation['checkedAt'] = batch
        observation['inventory']['checkedAt'] = ended
        observation['posts'][0]['metrics']['views']['observedAt'] = measured
        official_broker.apply(data, 'tiktok', observation)
        metric = data['videos'][0]['posts']['tiktok']['metrics']['views']
        self.assertEqual(metric['at'], measured)
        self.assertEqual(data['accounts'][0]['metrics']['followers']['at'], batch)
        self.assertEqual(data['discovery']['tiktok']['lastCompleteAt'], ended)
        self.assertEqual(data['discovery']['tiktok']['checkedAt'], ended)

    def test_malformed_metric_date_does_not_replace_prior_observation(self):
        data, observation = fixture()
        official_broker.apply(data, 'tiktok', observation)
        original = copy.deepcopy(data['videos'][0]['posts']['tiktok']['metrics']['views'])
        for bad in ['2020-01-01T00:00:00Z', '2099-01-01T00:00:00Z', '2026-11-04T12:00:00', None]:
            observation['posts'][0]['metrics']['views'].update(value=99, observedAt=bad)
            official_broker.apply(data, 'tiktok', observation)
            self.assertEqual(data['videos'][0]['posts']['tiktok']['metrics']['views'], original)

    def test_facebook_official_counter_preserves_primary_view_definition(self):
        target = {'url': 'https://www.facebook.com/reel/123', 'metrics': {'views': {'value': 900, 'at': '2026-11-04T00:00:00Z', 'source': 'https://www.facebook.com/reel/123', 'definition': 'Content Library Views'}}}
        prior = copy.deepcopy(target['metrics']['views'])
        at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        official_broker.metrics(target, {'facebookOfficialVideoViews': {'value': 12, 'apiMetric': 'video.views', 'observedAt': at, 'definition': 'Graph Video.views; equivalence unverified'}}, at)
        self.assertEqual(target['metrics']['views'], prior)
        self.assertEqual(target['metrics']['facebookOfficialVideoViews']['value'], 12)
        self.assertEqual(target['metrics']['facebookOfficialVideoViews']['apiMetric'], 'video.views')
        self.assertIn('unverified', target['metrics']['facebookOfficialVideoViews']['definition'])

    def test_legacy_facebook_broker_views_are_not_primary_views(self):
        data, observation = fixture()
        data['accounts'][0].update(id='facebook', expectedPageId='456', url='https://www.facebook.com/profile.php?id=456')
        observation.update(platform='facebook', owner={'id': '456'})
        observation['posts'][0].update(url='https://www.facebook.com/reel/123', metrics={'views': {'value': 12, 'apiMetric': 'video.views'}})
        official_broker.apply(data, 'facebook', observation)
        metrics = data['videos'][0]['posts']['facebook']['metrics']
        self.assertNotIn('views', metrics)
        self.assertEqual(metrics['facebookOfficialVideoViews']['value'], 12)

    def test_exact_official_post_fills_only_a_missing_publication_date(self):
        data, observation = fixture()
        official_broker.apply(data, 'tiktok', observation)
        video = data['videos'][0]
        video['publishedAt'] = None
        video.update(title='Preserve title', assetUrl='https://drive.google.com/file/d/original/view')
        official_broker.apply(data, 'tiktok', observation)
        self.assertEqual(data['videos'][0]['publishedAt'], observation['posts'][0]['publishedAt'])
        self.assertEqual(data['videos'][0]['title'], 'Preserve title')
        self.assertEqual(data['videos'][0]['assetUrl'], 'https://drive.google.com/file/d/original/view')
        known = data['videos'][0]['publishedAt']
        observation['posts'][0]['publishedAt'] = '2026-10-22T00:00:00Z'
        official_broker.apply(data, 'tiktok', observation)
        self.assertEqual(data['videos'][0]['publishedAt'], known)

    def test_new_legitimate_full_inventory_retains_historical_revocations(self):
        data, observation = fixture()
        revoked = [{'at': '2026-11-03T15:24:43.937Z', 'recordedAt': '2026-11-03T21:00:00Z', 'fallbackAt': '2026-11-03T13:39:48.715Z', 'reason': 'Grid terminal not independently verified'}]
        data['discovery'] = {'tiktok': {'lastCompleteAt': revoked[0]['fallbackAt'], 'revokedCompleteChecks': copy.deepcopy(revoked)}}
        official_broker.apply(data, 'tiktok', observation)
        self.assertEqual(data['discovery']['tiktok']['revokedCompleteChecks'], revoked)
        self.assertEqual(data['discovery']['tiktok']['lastCompleteAt'], observation['checkedAt'])

    def test_stale_and_future_responses_do_not_claim_freshness(self):
        for at in ['2020-01-01T00:00:00Z', '2099-01-01T00:00:00Z']:
            data, observation = fixture()
            observation['checkedAt'] = at
            with self.assertRaises(ValueError): official_broker.apply(data, 'tiktok', observation)

    def test_no_credentials_means_no_network_request(self):
        data, _ = fixture()
        with patch.dict(official_broker.os.environ, {}, clear=True), patch.object(official_broker, 'request') as request:
            self.assertEqual(official_broker.refresh(data), data)
            request.assert_not_called()

    def test_only_registered_platforms_are_requested_for_new_channel(self):
        data, _ = fixture()
        data['channelId'] = 'no-code-kevin'
        data['accounts'][0].update(expectedHandle='nocodekevin', url='https://www.tiktok.com/@nocodekevin')
        with patch.dict(official_broker.os.environ, {'SOCIAL_STATS_BROKER_URL': 'https://script.google.com/macros/s/test/exec', 'SOCIAL_STATS_BROKER_KEY': 'a' * 64}, clear=True), patch.object(official_broker, 'request', side_effect=ValueError('CONFIGURATION_REQUIRED')) as request:
            self.assertEqual(official_broker.refresh(data), data)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.args[:2], ('no-code-kevin', 'tiktok'))

    def test_broker_destination_must_be_an_apps_script_deployment(self):
        with self.assertRaises(ValueError): official_broker.request('indian-builds', 'tiktok', [], 'https://wrong.example/collect', 'x' * 64)

    def test_invalid_second_post_does_not_apply_first_one(self):
        data, observation = fixture()
        observation['posts'].append(dict(observation['posts'][0], id='456', url='https://wrong.example/456'))
        original = copy.deepcopy(data)
        with self.assertRaises(ValueError): official_broker.apply(data, 'tiktok', observation)
        self.assertEqual(data, original)


if __name__ == '__main__': unittest.main()
