import copy, json, pathlib, tempfile, unittest
from import_browser_snapshot import merge_bundle

def metric(value, at, url):return {'value':value,'at':at,'source':url,'approximate':False}

class BrowserBundleTests(unittest.TestCase):
    def fixture(self, root):
        data=root/'data';data.mkdir()
        channels=[];snapshots={}
        for cid in ['cooked-dev','indian-builds','dont-get-traced']:
            directory=data if cid=='cooked-dev' else data/cid;directory.mkdir(exist_ok=True)
            account={'id':'tiktok','name':'TikTok','url':'https://www.tiktok.com/@'+cid,'handle':cid,'status':'partial','metrics':{}}
            url=account['url']+'/video/123'
            d={'version':1,'generatedAt':'2026-10-28T10:00:00Z','lastAttemptAt':'2026-10-28T10:00:00Z','accounts':[account], 'videos':[{'id':'v1','number':1,'title':'Video','assetUrl':'https://drive.google.com/file/d/original/view','posts':{'tiktok':{'id':'123','url':url,'metrics':{'views':metric(20,'2026-10-28T10:00:00Z',url)}}}}], 'history':[]}
            if cid!='cooked-dev':d['channelId']=cid
            (directory/'latest.json').write_text(json.dumps(d));snapshots[cid]=copy.deepcopy(d)
            channels.append({'id':cid,'dataPath':str((directory/'latest.json').relative_to(root))})
        (data/'channels.json').write_text(json.dumps({'channels':channels}));(data/'publications.json').write_text(json.dumps({'groups':[]}))
        return {'version':1,'repository':'Jautis5/cooked-dev-stats','startedAt':'2026-10-28T09:00:00Z','capturedAt':'2026-10-28T09:01:00Z','channels':snapshots}

    def test_old_capture_keeps_newer_metric_and_original(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);bundle=self.fixture(root)
            for snapshot in bundle['channels'].values():
                post=snapshot['videos'][0]['posts']['tiktok'];post['metrics']['views']=metric(1,'2026-10-28T09:00:00Z',post['url'])
            result=merge_bundle(root,bundle)
            for path,d in result.values():
                self.assertEqual(d['videos'][0]['posts']['tiktok']['metrics']['views']['value'],20)
                self.assertEqual(d['videos'][0]['assetUrl'],'https://drive.google.com/file/d/original/view')

    def test_invalid_last_channel_does_not_partially_write(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);bundle=self.fixture(root);before=(root/'data/latest.json').read_bytes()
            bundle['channels']['dont-get-traced']['accounts'][0]['url']='https://www.tiktok.com/@other'
            with self.assertRaises(ValueError):merge_bundle(root,bundle)
            self.assertEqual((root/'data/latest.json').read_bytes(),before)

if __name__=='__main__':unittest.main()
