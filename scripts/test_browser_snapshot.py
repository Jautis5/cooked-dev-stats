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

    def test_subset_keeps_other_channels_and_older_health_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);bundle=self.fixture(root)
            other=root/'data/indian-builds/latest.json';before=other.read_bytes()
            previous={'completedAt':'2026-10-28T08:00:00Z','channels':{'indian-builds':{'checkedAt':'2026-10-28T08:00:00Z','metricsUpdated':7}}}
            (root/'data/browser-health.json').write_text(json.dumps(previous))
            bundle['channels']={'cooked-dev':bundle['channels']['cooked-dev']}
            merge_bundle(root,bundle)
            health=json.loads((root/'data/browser-health.json').read_text())
            self.assertEqual(other.read_bytes(),before)
            self.assertEqual(health['channels']['indian-builds'],previous['channels']['indian-builds'])
            self.assertEqual(health['channels']['cooked-dev']['checkedAt'],bundle['capturedAt'])

    def test_browser_capture_preserves_cloud_health(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);bundle=self.fixture(root)
            cloud={'version':1,'provider':'GitHub Actions','status':'completed_with_gaps','completedAt':'2026-10-28T08:00:00Z','channels':{}}
            (root/'data/health.json').write_text(json.dumps(cloud))
            merge_bundle(root,bundle)
            self.assertEqual(json.loads((root/'data/health.json').read_text()),cloud)
            browser=json.loads((root/'data/browser-health.json').read_text())
            self.assertEqual(browser['provider'],'authorized_local_browser')
            self.assertEqual(browser['completedAt'],bundle['capturedAt'])

    def test_unknown_channel_does_not_partially_write(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);bundle=self.fixture(root);before=(root/'data/latest.json').read_bytes()
            bundle['channels']['unregistered']=copy.deepcopy(bundle['channels']['cooked-dev'])
            with self.assertRaises(ValueError):merge_bundle(root,bundle)
            self.assertEqual((root/'data/latest.json').read_bytes(),before)

    def test_three_channel_capture_still_works_after_fourth_registered(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);bundle=self.fixture(root)
            registry=json.loads((root/'data/channels.json').read_text())
            extra=root/'data/dumb-luck';extra.mkdir()
            fourth=copy.deepcopy(bundle['channels']['indian-builds']);fourth['channelId']='dumb-luck'
            (extra/'latest.json').write_text(json.dumps(fourth));before=(extra/'latest.json').read_bytes()
            registry['channels'].append({'id':'dumb-luck','dataPath':'data/dumb-luck/latest.json'})
            (root/'data/channels.json').write_text(json.dumps(registry))
            self.assertEqual(len(merge_bundle(root,bundle)),3)
            self.assertEqual((extra/'latest.json').read_bytes(),before)

    def test_equal_capture_times_keep_independent_channel_reports(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);bundle=self.fixture(root)
            first=copy.deepcopy(bundle);first['channels']={'cooked-dev':bundle['channels']['cooked-dev']}
            merge_bundle(root,first)
            before=json.loads((root/'data/browser-health.json').read_text())
            second=copy.deepcopy(bundle);second['channels']={'indian-builds':bundle['channels']['indian-builds']}
            merge_bundle(root,second)
            health=json.loads((root/'data/browser-health.json').read_text())
            self.assertEqual(health['completedAt'],bundle['capturedAt'])
            self.assertEqual(health['channels']['cooked-dev'],before['channels']['cooked-dev'])
            self.assertEqual(health['channels']['indian-builds']['checkedAt'],bundle['capturedAt'])

    def test_older_global_capture_updates_newer_channel_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);bundle=self.fixture(root)
            previous={'provider':'authorized_local_browser','startedAt':'2026-10-28T11:59:00Z',
                      'completedAt':'2026-10-28T12:00:00Z','channels':{
                          'cooked-dev':{'checkedAt':'2026-10-28T12:00:00Z','metricsUpdated':9},
                          'indian-builds':{'checkedAt':'2026-10-28T08:00:00Z','metricsUpdated':7}}}
            (root/'data/browser-health.json').write_text(json.dumps(previous))
            bundle['channels']={'indian-builds':bundle['channels']['indian-builds']}
            merge_bundle(root,bundle)
            health=json.loads((root/'data/browser-health.json').read_text())
            self.assertEqual(health['completedAt'],previous['completedAt'])
            self.assertEqual(health['startedAt'],previous['startedAt'])
            self.assertEqual(health['channels']['cooked-dev'],previous['channels']['cooked-dev'])
            self.assertEqual(health['channels']['indian-builds']['checkedAt'],bundle['capturedAt'])

    def test_stale_capture_preserves_newer_same_channel_health(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);bundle=self.fixture(root)
            previous={'provider':'authorized_local_browser','completedAt':'2026-10-28T12:00:00Z',
                      'channels':{'cooked-dev':{'checkedAt':'2026-10-28T11:00:00Z','metricsUpdated':9}}}
            (root/'data/browser-health.json').write_text(json.dumps(previous))
            bundle['channels']={'cooked-dev':bundle['channels']['cooked-dev']}
            merge_bundle(root,bundle)
            self.assertEqual(json.loads((root/'data/browser-health.json').read_text()),previous)

    def test_equal_channel_capture_time_recomputes_cumulative_metrics(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);bundle=self.fixture(root)
            bundle['startedAt']='2026-10-28T10:01:00Z';bundle['capturedAt']='2026-10-28T10:02:00Z'
            bundle['channels']={'cooked-dev':bundle['channels']['cooked-dev']}
            merge_bundle(root,bundle)
            before=json.loads((root/'data/browser-health.json').read_text())
            self.assertEqual(before['channels']['cooked-dev']['metricsUpdated'],0)
            post=bundle['channels']['cooked-dev']['videos'][0]['posts']['tiktok']
            post['metrics']['likes']=metric(3,'2026-10-28T10:01:30Z',post['url'])
            merge_bundle(root,bundle)
            health=json.loads((root/'data/browser-health.json').read_text())
            self.assertEqual(health['channels']['cooked-dev']['checkedAt'],bundle['capturedAt'])
            self.assertEqual(health['channels']['cooked-dev']['metricsUpdated'],1)

    def test_publisher_keeps_equal_time_channel_reports_during_git_race(self):
        import subprocess
        from publish_refresh import publish
        def git(root,*args):
            return subprocess.run(['git','-C',str(root),*args],check=True,capture_output=True,text=True).stdout.strip()
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);remote=root/'remote.git';writer=root/'writer';other=root/'other'
            subprocess.run(['git','init','--bare','--initial-branch=main',str(remote)],check=True,capture_output=True)
            subprocess.run(['git','clone',str(remote),str(writer)],check=True,capture_output=True)
            git(writer,'config','user.name','Test');git(writer,'config','user.email','test@example.com')
            bundle=self.fixture(writer);at=bundle['capturedAt']
            seed={'provider':'authorized_local_browser','completedAt':at,
                  'channels':{'indian-builds':{'checkedAt':at,'marker':'seed'}}}
            cloud={'provider':'GitHub Actions','completedAt':'2026-10-28T08:00:00Z'}
            (writer/'data/browser-health.json').write_text(json.dumps(seed))
            (writer/'data/health.json').write_text(json.dumps(cloud))
            git(writer,'add','.');git(writer,'commit','-m','seed');git(writer,'push','origin','main')
            subprocess.run(['git','clone',str(remote),str(other)],check=True,capture_output=True)
            git(other,'config','user.name','Other');git(other,'config','user.email','other@example.com')
            local={'provider':'authorized_local_browser','completedAt':at,
                   'channels':{'cooked-dev':{'checkedAt':at,'marker':'local'}}}
            (writer/'data/browser-health.json').write_text(json.dumps(local))
            def race(attempt):
                if attempt:return
                concurrent=copy.deepcopy(seed);concurrent['channels']['indian-builds']['marker']='concurrent'
                concurrent['channels']['dont-get-traced']={'checkedAt':at,'marker':'concurrent'}
                (other/'data/browser-health.json').write_text(json.dumps(concurrent))
                (other/'data/health.json').write_text(json.dumps(dict(cloud,completedAt='2026-10-28T11:00:00Z')))
                git(other,'add','.');git(other,'commit','-m','concurrent health');git(other,'push','origin','main')
            publish(writer,before_push=race)
            health=json.loads(git(remote,'show','main:data/browser-health.json'))
            self.assertEqual(health['completedAt'],at)
            self.assertEqual(set(health['channels']),{'cooked-dev','indian-builds','dont-get-traced'})
            self.assertEqual(health['channels']['cooked-dev'],local['channels']['cooked-dev'])
            self.assertEqual(health['channels']['indian-builds']['marker'],'concurrent')
            self.assertEqual(health['channels']['dont-get-traced']['checkedAt'],at)
            self.assertEqual(json.loads(git(remote,'show','main:data/health.json'))['completedAt'],'2026-10-28T11:00:00Z')
            self.assertEqual(json.loads((writer/'data/browser-health.json').read_text()),local)

if __name__=='__main__':unittest.main()
