import json
import pathlib
import unittest

from snapshot_merge import validate

ROOT = pathlib.Path(__file__).resolve().parents[1]


class DumbLuckIdentityTests(unittest.TestCase):
    def test_tracker_uses_owner_confirmed_accounts(self):
        channels = json.loads((ROOT / 'data/channels.json').read_text())['channels']
        channel = next(c for c in channels if c['id'] == 'dumb-luck')
        data = json.loads((ROOT / channel['dataPath']).read_text())
        self.assertEqual(data['channelId'], 'dumb-luck')
        accounts = {a['id']: a for a in data['accounts']}
        self.assertEqual(accounts['instagram']['url'], 'https://www.instagram.com/duumb_luck/')
        self.assertEqual(accounts['instagram']['expectedHandle'], 'duumb_luck')
        self.assertEqual(accounts['tiktok']['url'], 'https://www.tiktok.com/@duumbluck')
        self.assertEqual(accounts['tiktok']['expectedHandle'], 'duumbluck')
        self.assertEqual(accounts['youtube']['expectedChannelId'], 'UCB-BqPU60vRfUWGalt6fRtQ')
        self.assertEqual(accounts['youtube']['url'], 'https://www.youtube.com/channel/UCB-BqPU60vRfUWGalt6fRtQ')
        validate(data)


if __name__ == '__main__':
    unittest.main()
