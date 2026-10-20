import copy, datetime, json, pathlib, unittest
from unittest.mock import patch
import collect_channels as c
from import_channel_capture import merge

ROOT=pathlib.Path(__file__).resolve().parents[1]
class ChannelSafety(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((ROOT/'data/indian-builds/latest.json').read_text())
        self.now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    def batch(self,url='https://www.tiktok.com/@indiaanbuilds'):
        return {'channelId':'indian-builds','platforms':{'tiktok':{'browserProfile':'lostastronaut.space','accountUrl':url,'observedAt':self.now,'profileMetrics':{},'posts':[]}}}
    def test_cooked_dev_cannot_be_imported_into_indian_builds(self):
        with self.assertRaises(ValueError):merge(self.data,self.batch('https://www.tiktok.com/@cooked_dev_'))
    def test_missing_metric_keeps_date_and_zero_is_preserved(self):
        before=copy.deepcopy(self.data);out=merge(self.data,self.batch())
        self.assertEqual(out['accounts'][1]['metrics']['followers'],before['accounts'][1]['metrics']['followers'])
        self.assertEqual(out['accounts'][1]['metrics']['followers']['value'],0)
        self.assertEqual(self.data,before)
    def test_legacy_and_wrong_authors_cannot_be_adopted(self):
        self.assertFalse(c.tracked_item(self.data,{'id':'999','author':{'uniqueId':'cooked_dev_'},'createTime':2000000000},'indiaanbuilds'))
        legacy=self.data['tracking']['excludedPostIds']['tiktok'][0]
        self.assertFalse(c.tracked_item(self.data,{'id':legacy,'author':{'uniqueId':'indiaanbuilds'},'createTime':2000000000},'indiaanbuilds'))
        self.assertFalse(c.tracked_item(self.data,{'id':'999','author':{'uniqueId':'indiaanbuilds'},'createTime':1},'indiaanbuilds'))
    def test_matching_new_public_video_has_no_guessed_drive_or_instagram(self):
        batch=self.batch();batch['platforms']['tiktok']['posts']=[{'id':'999','url':'https://www.tiktok.com/@indiaanbuilds/video/999','public':True,'caption':'A new build','metrics':{'views':0}}]
        out=merge(self.data,batch);v=out['videos'][-1]
        self.assertIsNone(v['assetUrl']);self.assertEqual(list(v['posts']),['tiktok'])
        self.assertEqual(v['posts']['tiktok']['metrics']['views']['value'],0)
    def test_wrong_profile_never_updates_counts(self):
        scope={'userInfo':{'user':{'uniqueId':'cooked_dev_'},'stats':{'followerCount':999}}}
        with patch.object(c.base,'request',return_value='ignored'),patch.object(c.base,'state',return_value={'webapp.user-detail':scope}):out=c.refresh(copy.deepcopy(self.data))
        self.assertEqual(out['accounts'][1]['metrics']['followers']['value'],0)
    def test_registry_separates_sources(self):
        registry=json.loads((ROOT/'data/channels.json').read_text())['channels']
        self.assertEqual(len({r['id'] for r in registry}),len(registry))
        self.assertEqual(len({r['dataPath'] for r in registry}),len(registry))
        for channel in registry:
            data=json.loads((ROOT/channel['dataPath']).read_text())
            self.assertEqual(len({v['id'] for v in data['videos']}),len(data['videos']))
            if channel['id']=='indian-builds':
                self.assertEqual(data['channelId'],channel['id'])
                self.assertTrue(all(a['expectedHandle']=='indiaanbuilds' for a in data['accounts']))
                excluded=data['tracking']['excludedPostIds']
                self.assertTrue(all(p['id'] not in excluded.get(platform,[]) for v in data['videos'] for platform,p in v['posts'].items()))
if __name__=='__main__':unittest.main()
