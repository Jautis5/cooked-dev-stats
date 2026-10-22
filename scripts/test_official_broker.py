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

    def test_broker_destination_must_be_an_apps_script_deployment(self):
        with self.assertRaises(ValueError): official_broker.request('indian-builds', 'tiktok', [], 'https://wrong.example/collect', 'x' * 64)

    def test_invalid_second_post_does_not_apply_first_one(self):
        data, observation = fixture()
        observation['posts'].append(dict(observation['posts'][0], id='456', url='https://wrong.example/456'))
        original = copy.deepcopy(data)
        with self.assertRaises(ValueError): official_broker.apply(data, 'tiktok', observation)
        self.assertEqual(data, original)


if __name__ == '__main__': unittest.main()
