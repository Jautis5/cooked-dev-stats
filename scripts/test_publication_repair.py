import copy, json, pathlib, unittest
from unittest.mock import patch
import collect as base
from publications import reconcile
from public_fallbacks import tiktok_embed, youtube_shorts, x_public
from refresh_all import metric_health

ROOT = pathlib.Path(__file__).resolve().parents[1]


class PublicationRepairTests(unittest.TestCase):
    def test_receipts_join_existing_rows_without_losing_metrics(self):
        data = json.loads((ROOT/'data/latest.json').read_text())
        reconcile(data)
        for number in [5, 6]:
            video = next(v for v in data['videos'] if v['number'] == number)
            self.assertTrue(all(p in video['posts'] for p in ['instagram','tiktok','youtube','facebook','x']))
            youtube = video['posts']['youtube']
            self.assertEqual(sum(v['posts'].get('youtube',{}).get('id') == youtube['id'] for v in data['videos']), 1)
        prior = copy.deepcopy(data)
        self.assertEqual(reconcile(data), prior)

    def test_receipt_cannot_attach_another_channels_publications(self):
        data = json.loads((ROOT/'data/indian-builds/latest.json').read_text())
        registry = json.loads((ROOT/'data/publications.json').read_text())
        group = next(g for g in registry['groups'] if g['channelId'] == 'indian-builds')
        group['owners']['youtube'] = 'UCNPkHyLJotjamsFxts47T2A'
        with self.assertRaises(ValueError): reconcile(data, registry)

    def test_known_publication_invalidates_old_empty_state(self):
        data = json.loads((ROOT/'data/indian-builds/latest.json').read_text())
        reconcile(data)
        for account in data['accounts']:
            if account['id'] in ['youtube','facebook','x']:
                self.assertNotIn('trackedEmptyConfirmedAt', account)
                self.assertNotEqual(account.get('metrics',{}).get('trackedPublishedCount',{}).get('value'), 0)

    def test_tiktok_embed_discovers_missing_public_posts_with_owner_guard(self):
        data = {'videos':[], 'tracking':{}}
        account = {'handle':'right','url':'https://www.tiktok.com/@right'}
        profile = {'userInfo':{'uniqueId':'right'}, 'videoList':[
            {'id':'123','authorUniqueId':'right','privateItem':False,'desc':'New video','playCount':0},
            {'id':'456','authorUniqueId':'wrong','privateItem':False,'desc':'Suggestion','playCount':100}]}
        page = '<script id="__FRONTITY_CONNECT_STATE__">'+json.dumps({'source':{'data':{'/embed/@right':profile}}})+'</script>'
        with patch.object(base,'request',return_value=page):
            result = tiktok_embed(data,account)
        self.assertEqual(result['newVideos'],1)
        self.assertFalse(result['complete'])
        self.assertEqual(data['videos'][0]['posts']['tiktok']['metrics']['views']['value'],0)

    def test_youtube_fallback_refreshes_known_views_without_adopting_undated_legacy(self):
        channel = 'UCgHxdk2zTRXwsoCrICSwiRg'
        known = {'id':'abcdefghijk','url':'https://www.youtube.com/shorts/abcdefghijk','metrics':{}}
        data = {'tracking':{'startedAt':'2026-10-20T00:00:00Z'}, 'videos':[{'id':'v','number':1,'posts':{'youtube':known}}]}
        short = lambda identity: {'shortsLockupViewModel':{'onTap':{'innertubeCommand':{'reelWatchEndpoint':{'videoId':identity},'commandMetadata':{'webCommandMetadata':{'url':'/shorts/'+identity}}}},'overlayMetadata':{'primaryText':{'content':'Video'},'secondaryText':{'content':'1.2K views'}}}}
        initial = {'metadata':{'channelMetadataRenderer':{'externalId':channel}},'contents':{'twoColumnBrowseResultsRenderer':{'tabs':[{'tabRenderer':{'selected':True,'title':'Shorts','content':[short('abcdefghijk'),short('lmnopqrstuv')]}}]}}}
        with patch.object(base,'request',return_value='var ytInitialData = '+json.dumps(initial)+';'):
            youtube_shorts(data,{'expectedChannelId':channel})
        self.assertEqual(len(data['videos']),1)
        self.assertEqual(known['metrics']['views']['value'],1200)
        self.assertTrue(known['metrics']['views']['approximate'])

    def test_x_embed_never_turns_likes_into_views_and_rejects_wrong_owner(self):
        post = {'id':'123','url':'https://x.com/right/status/123','metrics':{'views':{'value':17,'at':'old'}}}
        payload = {'id_str':'123','user':{'screen_name':'right'},'mediaDetails':[{'type':'video'}],'favorite_count':0,'conversation_count':2}
        with patch.object(base,'request',return_value=json.dumps(payload)):
            x_public(post,{'handle':'right'})
        self.assertEqual(post['metrics']['views'],{'value':17,'at':'old'})
        self.assertEqual(post['metrics']['likes']['value'],0)
        with patch.object(base,'request',return_value=json.dumps(payload)):
            with self.assertRaises(ValueError): x_public(post,{'handle':'wrong'})

    def test_health_counts_view_freshness_separately_from_other_metrics(self):
        data = {'accounts':[{'id':'x','name':'X','status':'partial','metrics':{}}], 'videos':[{'posts':{'x':{'metrics':{'views':{'value':10,'at':'2026-10-20T00:00:00Z'},'likes':{'value':1,'at':base.NOW}}}}}]}
        report = metric_health(data, base.NOW)['x']
        self.assertEqual(report['metricsUpdated'],1)
        self.assertEqual(report['viewsUpdated'],0)
        self.assertFalse(report['inventoryComplete'])


if __name__ == '__main__': unittest.main()
