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
                self.assertTrue(all(a.get('expectedHandle')=='indiaanbuilds' for a in data['accounts'] if a['id'] in ['instagram','tiktok']))
                facebook=next(a for a in data['accounts'] if a['id']=='facebook')
                self.assertEqual(facebook['expectedPageId'],'61594164374065')
                self.assertEqual(facebook['url'],'https://www.facebook.com/profile.php?id=61594164374065')
                x=next(a for a in data['accounts'] if a['id']=='x')
                self.assertEqual(x['expectedHandle'],'IndiaanBuilds')
                self.assertEqual(x['url'],'https://x.com/IndiaanBuilds')
                excluded=data['tracking']['excludedPostIds']
                self.assertTrue(all(p['id'] not in excluded.get(platform,[]) for v in data['videos'] for platform,p in v['posts'].items()))
    def test_cooked_facebook_cannot_update_indian_builds(self):
        batch={'channelId':'indian-builds','platforms':{'facebook':{'browserProfile':'lostastronaut.space','accountUrl':'https://www.facebook.com/profile.php?id=61595564490107','observedAt':self.now,'profileMetrics':{'followers':999},'posts':[]}}}
        with self.assertRaises(ValueError):merge(self.data,batch)
    def test_facebook_accepts_only_matching_real_reel_id(self):
        batch={'channelId':'indian-builds','platforms':{'facebook':{'browserProfile':'lostastronaut.space','accountUrl':'https://www.facebook.com/profile.php?id=61594164374065','observedAt':self.now,'posts':[{'id':'123456789','url':'https://www.facebook.com/reel/123456789','public':True,'caption':'New build','metrics':{'views':0}}]}}}
        out=merge(self.data,batch)
        self.assertEqual(out['videos'][-1]['posts']['facebook']['metrics']['views']['value'],0)
        self.assertIsNone(out['videos'][-1]['assetUrl'])
        batch['platforms']['facebook']['posts'][0]['url']='https://www.facebook.com/reel/987654321'
        with self.assertRaises(ValueError):merge(self.data,batch)
    def test_x_rejects_cooked_dev_and_text_posts(self):
        batch={'channelId':'indian-builds','platforms':{'x':{'browserProfile':'lostastronaut.space','accountUrl':'https://x.com/IndiaanBuilds','observedAt':self.now,'posts':[{'id':'123456789','url':'https://x.com/Cooked_Deev/status/123456789','public':True,'isVideo':True,'caption':'A build','metrics':{'views':0}}]}}}
        with self.assertRaises(ValueError):merge(self.data,batch)
        batch['platforms']['x']['posts'][0]['url']='https://x.com/IndiaanBuilds/status/123456789'
        batch['platforms']['x']['posts'][0]['isVideo']=False
        with self.assertRaises(ValueError):merge(self.data,batch)
        batch['platforms']['x']['posts'][0]['isVideo']=True
        out=merge(self.data,batch)
        self.assertEqual(out['videos'][-1]['posts']['x']['metrics']['views']['value'],0)
        self.assertIsNone(out['videos'][-1]['assetUrl'])
if __name__=='__main__':unittest.main()
