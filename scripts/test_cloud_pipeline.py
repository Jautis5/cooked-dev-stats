import copy, json, pathlib, subprocess, tempfile, unittest
from unittest.mock import patch
from snapshot_merge import merge_snapshot, validate
from publish_refresh import publish


def metric(value, at, source='https://example.com/video'):
    return {'value': value, 'at': at, 'source': source, 'approximate': False}


def fixture():
    return {'version': 1, 'accounts': [{'id': 'youtube', 'name': 'YouTube', 'url': 'https://example.com/channel', 'status': 'partial', 'metrics': {}}],
            'videos': [{'id': 'v1', 'number': 1, 'title': 'A video', 'caption': 'A video', 'assetUrl': None, 'posts': {'youtube': {'id': 'abcdefghijk', 'url': 'https://example.com/video', 'metrics': {'views': metric(10, '2026-10-20T09:00:00Z')}}}}],
            'lastAttemptAt': '2026-10-20T09:00:00Z', 'history': []}


class MergeTests(unittest.TestCase):
    def test_newest_values_and_remote_asset_survive(self):
        remote = fixture(); candidate = copy.deepcopy(remote)
        remote['videos'][0]['assetUrl'] = 'https://drive.google.com/verified-original'
        remote['videos'][0]['posts']['youtube']['metrics']['likes'] = metric(4, '2026-10-20T11:00:00Z')
        candidate['videos'][0]['posts']['youtube']['metrics']['views'] = metric(20, '2026-10-20T10:00:00Z')
        candidate['videos'][0]['posts']['youtube']['metrics']['likes'] = metric(1, '2026-10-20T08:00:00Z')
        out = merge_snapshot(remote, candidate)
        self.assertEqual(out['videos'][0]['assetUrl'], remote['videos'][0]['assetUrl'])
        self.assertEqual(out['videos'][0]['posts']['youtube']['metrics']['views']['value'], 20)
        self.assertEqual(out['videos'][0]['posts']['youtube']['metrics']['likes']['value'], 4)
        self.assertEqual(remote['videos'][0]['posts']['youtube']['metrics']['views']['value'], 10)

    def test_removed_record_is_not_resurrected(self):
        base = fixture(); remote = copy.deepcopy(base); remote['videos'] = []
        self.assertEqual(merge_snapshot(remote, base, base)['videos'], [])

    def test_equal_ids_on_different_channels_are_never_merged(self):
        a = fixture(); b = fixture(); b['channelId'] = 'indian-builds'
        with self.assertRaises(ValueError): merge_snapshot(a, b)

    def test_metric_origin_and_unknown_are_not_forged(self):
        a = fixture(); b = copy.deepcopy(a)
        b['videos'][0]['posts']['youtube']['metrics']['views'] = metric(0, '2026-10-20T11:00:00Z', 'https://wrong.example')
        self.assertEqual(merge_snapshot(a, b)['videos'][0]['posts']['youtube']['metrics']['views']['value'], 10)
        b['videos'][0]['posts']['youtube']['metrics']['views'] = metric(None, '2026-10-20T11:00:00Z')
        self.assertEqual(merge_snapshot(a, b)['videos'][0]['posts']['youtube']['metrics']['views']['value'], 10)
        b['videos'][0]['posts']['youtube']['metrics']['views'] = metric(0, '2026-10-20T11:00:00Z')
        self.assertEqual(merge_snapshot(a, b)['videos'][0]['posts']['youtube']['metrics']['views']['value'], 0)
        validate(merge_snapshot(a, b))

    def test_duplicate_post_is_not_adopted_under_another_video(self):
        a = fixture(); b = copy.deepcopy(a); b['videos'][0]['id'] = 'new-wrapper'
        self.assertEqual(len(merge_snapshot(a, b)['videos']), 1)

    def test_actual_git_push_race_retains_both_updates(self):
        def git(root, *args):
            return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True, text=True).stdout.strip()
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder); remote = root / 'remote.git'; writer = root / 'writer'; other = root / 'other'
            subprocess.run(['git', 'init', '--bare', '--initial-branch=main', str(remote)], check=True, capture_output=True)
            subprocess.run(['git', 'clone', str(remote), str(writer)], check=True, capture_output=True)
            for key, value in [('user.name', 'Test'), ('user.email', 'test@example.com')]: git(writer, 'config', key, value)
            (writer / 'data').mkdir(); (writer / 'data/channels.json').write_text(json.dumps({'channels': [{'id': 'cooked-dev', 'dataPath': 'data/latest.json'}]}))
            (writer / 'data/latest.json').write_text(json.dumps(fixture()))
            (writer / 'README.md').write_text('source v1')
            git(writer, 'add', '.'); git(writer, 'commit', '-m', 'seed'); git(writer, 'push', 'origin', 'main')
            subprocess.run(['git', 'clone', str(remote), str(other)], check=True, capture_output=True)
            for key, value in [('user.name', 'Other'), ('user.email', 'other@example.com')]: git(other, 'config', key, value)
            candidate = fixture(); candidate['lastAttemptAt'] = '2026-10-20T10:00:00Z'
            candidate['videos'][0]['posts']['youtube']['metrics']['views'] = metric(20, '2026-10-20T10:00:00Z')
            (writer / 'data/latest.json').write_text(json.dumps(candidate))
            def race(attempt):
                if attempt: return
                changed = fixture(); changed['videos'][0]['assetUrl'] = 'https://drive.google.com/concurrent-original'
                changed['videos'][0]['posts']['youtube']['metrics']['likes'] = metric(9, '2026-10-20T11:00:00Z')
                (other / 'data/latest.json').write_text(json.dumps(changed)); (other / 'README.md').write_text('source v2')
                git(other, 'add', '.'); git(other, 'commit', '-m', 'concurrent browser update'); git(other, 'push', 'origin', 'main')
            commit = publish(writer, before_push=race)
            output = json.loads(git(remote, 'show', 'main:data/latest.json'))
            self.assertEqual(output['videos'][0]['assetUrl'], 'https://drive.google.com/concurrent-original')
            self.assertEqual(output['videos'][0]['posts']['youtube']['metrics']['views']['value'], 20)
            self.assertEqual(output['videos'][0]['posts']['youtube']['metrics']['likes']['value'], 9)
            self.assertEqual(git(remote, 'show', 'main:README.md'), 'source v2')
            self.assertEqual(git(remote, 'rev-parse', 'main'), commit)
            self.assertEqual(json.loads((writer / 'data/latest.json').read_text()), candidate, 'Caller checkout must remain unchanged')

    def test_cloud_and_browser_health_survive_concurrent_publish(self):
        def git(root,*args):
            return subprocess.run(['git','-C',str(root),*args],check=True,capture_output=True,text=True).stdout.strip()
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);remote=root/'remote.git';writer=root/'writer';other=root/'other'
            subprocess.run(['git','init','--bare','--initial-branch=main',str(remote)],check=True,capture_output=True)
            subprocess.run(['git','clone',str(remote),str(writer)],check=True,capture_output=True)
            for key,val in [('user.name','Test'),('user.email','test@example.com')]:git(writer,'config',key,val)
            (writer/'data').mkdir();(writer/'data/channels.json').write_text(json.dumps({'channels':[{'id':'cooked-dev','dataPath':'data/latest.json'}]}));(writer/'data/latest.json').write_text(json.dumps(fixture()))
            old={'provider':'GitHub Actions','completedAt':'2026-10-20T09:00:00Z'};(writer/'data/health.json').write_text(json.dumps(old))
            git(writer,'add','.');git(writer,'commit','-m','seed');git(writer,'push','origin','main')
            subprocess.run(['git','clone',str(remote),str(other)],check=True,capture_output=True)
            for key,val in [('user.name','Other'),('user.email','other@example.com')]:git(other,'config',key,val)
            browser={'provider':'authorized_local_browser','completedAt':'2026-10-20T10:00:00Z'};(writer/'data/browser-health.json').write_text(json.dumps(browser))
            def race(attempt):
                if attempt:return
                newer={'provider':'GitHub Actions','completedAt':'2026-10-20T11:00:00Z'};(other/'data/health.json').write_text(json.dumps(newer));git(other,'add','.');git(other,'commit','-m','new cloud');git(other,'push','origin','main')
            publish(writer,before_push=race)
            self.assertEqual(json.loads(git(remote,'show','main:data/health.json'))['completedAt'],'2026-10-20T11:00:00Z')
            self.assertEqual(json.loads(git(remote,'show','main:data/browser-health.json')),browser)

    def test_publication_moves_keep_new_metrics_and_measured_zero(self):
        for candidate_already_joined in [False, True]:
            with self.subTest(candidate_already_joined=candidate_already_joined), tempfile.TemporaryDirectory() as folder:
                from publications import reconcile
                def git(root, *args):
                    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True, text=True).stdout.strip()
                root = pathlib.Path(folder); remote = root / 'remote.git'; writer = root / 'writer'
                subprocess.run(['git', 'init', '--bare', '--initial-branch=main', str(remote)], check=True, capture_output=True)
                subprocess.run(['git', 'clone', str(remote), str(writer)], check=True, capture_output=True)
                git(writer, 'config', 'user.name', 'Test'); git(writer, 'config', 'user.email', 'test@example.com')
                data = fixture()
                data['channelId'] = 'cooked-dev'
                data['accounts'].append({'id':'x', 'name':'X', 'handle':'right', 'url':'https://x.com/right', 'status':'partial', 'metrics':{}})
                url = 'https://x.com/right/status/123'
                data['videos'].append({'id':'cloud-x', 'number':2, 'title':'New public post', 'posts':{'x':{'id':'123', 'url':url, 'metrics':{
                    'views':metric(10, '2026-10-20T09:00:00Z', url), 'likes':metric(9, '2026-10-20T11:00:00Z', url)}}}})
                ledger = {'groups':[{'id':'verified-original', 'channelId':'cooked-dev', 'videoId':'v1', 'number':1,
                    'caption':'A video', 'verifiedAt':'2026-10-20T09:30:00Z', 'evidence':'Original clip verified',
                    'owners':{'x':'right'}, 'posts':{'x':url}}]}
                (writer / 'data').mkdir()
                (writer / 'data/channels.json').write_text(json.dumps({'channels':[{'id':'cooked-dev', 'dataPath':'data/latest.json'}]}))
                (writer / 'data/latest.json').write_text(json.dumps(data))
                (writer / 'data/publications.json').write_text(json.dumps(ledger))
                git(writer, 'add', '.'); git(writer, 'commit', '-m', 'verified ledger awaiting reconciliation'); git(writer, 'push', 'origin', 'main')
                candidate = copy.deepcopy(data)
                if candidate_already_joined: reconcile(candidate, ledger)
                post = next(v['posts']['x'] for v in candidate['videos'] if 'x' in v['posts'])
                post['metrics'].update(views=metric(25, '2026-10-20T10:00:00Z', url),
                    likes=metric(1, '2026-10-20T08:00:00Z', url), saves=metric(0, '2026-10-20T10:00:00Z', url))
                (writer / 'data/latest.json').write_text(json.dumps(candidate))
                publish(writer)
                output = json.loads(git(remote, 'show', 'main:data/latest.json'))
                self.assertEqual(len(output['videos']), 1)
                observed = output['videos'][0]['posts']['x']['metrics']
                self.assertEqual(observed['views'], metric(25, '2026-10-20T10:00:00Z', url))
                self.assertEqual(observed['likes'], metric(9, '2026-10-20T11:00:00Z', url))
                self.assertEqual(observed['saves'], metric(0, '2026-10-20T10:00:00Z', url))
                self.assertEqual(json.loads((writer / 'data/latest.json').read_text()), candidate)


if __name__ == '__main__': unittest.main()

class PublicYouTubeTests(unittest.TestCase):
    def test_only_verified_public_video_can_update(self):
        import collect
        post = fixture()['videos'][0]['posts']['youtube']
        response = {'videoDetails': {'videoId': post['id'], 'channelId': 'correct', 'viewCount': '25'}, 'playabilityStatus': {'status': 'OK'}}
        with patch.object(collect, 'request', return_value='var ytInitialPlayerResponse = ' + json.dumps(response) + ';'):
            self.assertEqual(collect.youtube_video(copy.deepcopy(post), 'correct')['metrics']['views']['value'], 25)
            with self.assertRaises(ValueError): collect.youtube_video(copy.deepcopy(post), 'wrong')
        response['playabilityStatus']['status'] = 'LOGIN_REQUIRED'
        with patch.object(collect, 'request', return_value='var ytInitialPlayerResponse = ' + json.dumps(response) + ';'):
            with self.assertRaises(ValueError): collect.youtube_video(copy.deepcopy(post), 'correct')
