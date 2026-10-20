import copy, datetime, hashlib, pathlib, tempfile, unittest
from cloud_clock import collection_plan, clock_recovery_plan, ensure_successor, tick
from cloud_api import CloudAPI
from version_assets import version_assets

NOW=datetime.datetime.fromisoformat('2026-10-20T15:00:00+00:00').timestamp()
POLICY={'continuousClockEnabled':True,'intervalMinutes':15,'failureRetryMinutes':3,'clockStaleMinutes':35}
def ago(minutes):return datetime.datetime.fromtimestamp(NOW-minutes*60,datetime.timezone.utc).isoformat()
def run(age=20,status='completed',conclusion='success',id=1):
    return {'id':id,'created_at':ago(age),'status':status,'conclusion':conclusion}


class FakeAPI:
    def __init__(self,runs=None):
        self.policy=copy.deepcopy(POLICY);self.runs=runs or [];self.child=None;self.calls=[]
        self.private=False;self.uncertain=False;self.collect_error=False
    def file(self,path):return self.policy
    def call(self,path,body=None):
        self.calls.append((path,body))
        if path=='':return {'private':self.private}
        if path.startswith('/actions/workflows/refresh.yml/runs'):return {'workflow_runs':self.runs}
        if path.startswith('/actions/workflows/clock.yml/runs'):return {'workflow_runs':[self.child] if self.child else []}
        if path=='/actions/workflows/clock.yml/dispatches':
            self.child={'id':99,'display_title':'Cloud clock · after '+body['inputs']['predecessor'],'status':'queued'}
            if self.uncertain:raise TimeoutError('Response was lost after the successor was queued')
        if path=='/actions/workflows/refresh.yml/dispatches' and self.collect_error:raise TimeoutError('Temporary API failure')
        return {}


class ClockTests(unittest.TestCase):
    def test_an_extra_manual_refresh_cannot_defer_the_timed_cycle(self):
        self.assertEqual(collection_plan([run(0.5)],NOW,POLICY)['action'],'wait')
        self.assertEqual(collection_plan([run(14)],NOW,POLICY)['action'],'dispatch')
        self.assertEqual(collection_plan([run(15)],NOW,POLICY)['action'],'dispatch')
    def test_recent_collector_is_not_duplicated(self):
        self.assertEqual(collection_plan([run(2,'in_progress')],NOW,POLICY)['action'],'wait')
    def test_failed_collector_has_bounded_short_retry_cooldown(self):
        self.assertEqual(collection_plan([run(2,conclusion='failure')],NOW,POLICY)['action'],'wait')
        self.assertEqual(collection_plan([run(3,conclusion='failure')],NOW,POLICY)['action'],'dispatch')
    def test_stuck_collector_is_cancelled_before_replacement(self):
        self.assertEqual(collection_plan([run(60,'in_progress',id=7)],NOW,POLICY)['cancelRunIds'],[7])
    def test_waiting_environment_is_a_live_clock_and_not_restarted(self):
        self.assertEqual(clock_recovery_plan([run(12,'waiting')],NOW,POLICY)['action'],'wait')
        self.assertEqual(clock_recovery_plan([run(40,'waiting')],NOW,POLICY)['cancelRunIds'],[1])
    def test_disabled_policy_stops_the_chain(self):
        api=FakeAPI();api.policy['continuousClockEnabled']=False
        self.assertEqual(tick(api,12,NOW,lambda _:None)['action'],'disabled')
        self.assertFalse(any(body is not None for _,body in api.calls))
    def test_private_repository_cannot_enable_potentially_paid_work(self):
        api=FakeAPI();api.private=True
        with self.assertRaises(RuntimeError):tick(api,12,NOW,lambda _:None)
        self.assertFalse(any(body is not None for _,body in api.calls))
    def test_real_handoff_requests_next_production_timer(self):
        api=FakeAPI([run()]);result=tick(api,12,NOW,lambda _:None)
        self.assertEqual(result['successor'],99)
        bodies=dict((path,body) for path,body in api.calls if body)
        self.assertEqual(bodies['/actions/workflows/refresh.yml/dispatches']['inputs']['reason'],'continuous_clock')
        self.assertEqual(bodies['/actions/workflows/clock.yml/dispatches']['inputs']['timer'],'social-stats-clock')
    def test_ambiguous_handoff_response_does_not_create_duplicate_successors(self):
        api=FakeAPI();api.uncertain=True
        self.assertEqual(ensure_successor(api,12,lambda _:None)['id'],99)
        self.assertEqual(sum(path.endswith('/dispatches') for path,_ in api.calls),1)
        self.assertEqual(ensure_successor(api,12,lambda _:None)['id'],99)
        self.assertEqual(sum(path.endswith('/dispatches') for path,_ in api.calls),1)
    def test_collection_dispatch_failure_still_hands_off_the_clock(self):
        api=FakeAPI([run()]);api.collect_error=True
        with self.assertRaises(RuntimeError):tick(api,12,NOW,lambda _:None)
        self.assertIsNotNone(api.child)
    def test_token_cannot_be_sent_to_another_host(self):
        with self.assertRaises(ValueError):CloudAPI('owner/repo','not-a-real-token').call('https://example.com/')
    def test_changed_program_receives_a_new_browser_cache_key(self):
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp)
            (root/'index.html').write_text('<script src="app.js?v=old"></script><link href="styles.css">')
            (root/'app.js').write_text('old program');(root/'styles.css').write_text('style')
            version_assets(root);before=(root/'index.html').read_text()
            (root/'app.js').write_text('new program');version_assets(root)
            after=(root/'index.html').read_text()
            self.assertNotEqual(before,after)
            self.assertIn('app.js?v='+hashlib.sha256(b'new program').hexdigest()[:12],after)
            version_assets(root);self.assertEqual((root/'index.html').read_text(),after)


if __name__=='__main__':unittest.main()
