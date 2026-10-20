import copy, datetime, json, pathlib, unittest
from unittest.mock import patch
from watchdog import recovery_plan
from discover_public import discover_youtube
from collect import setmetric
NOW = datetime.datetime.fromisoformat('2026-10-20T12:00:00+00:00').timestamp()
CHANNEL = 'UCNPkHyLJotjamsFxts47T2A'
ACCOUNT = {'id': 'youtube', 'url': 'https://www.youtube.com/channel/' + CHANNEL}
POLICY = {'recoveryAfterMinutes': 45, 'retryCooldownMinutes': 15}


def ago(minutes): return datetime.datetime.fromtimestamp(NOW-minutes*60,datetime.timezone.utc).isoformat()


class WatchdogTests(unittest.TestCase):
    def health(self, age=5): return {'provider':'GitHub Actions','completedAt':ago(age),'status':'completed','channels':{'one':{'platforms':{'facebook':{'status':'unavailable'}}}}}
    def test_recent_partial_source_access_does_not_trigger_retry_storm(self):
        self.assertEqual(recovery_plan([], self.health(), NOW, POLICY)['action'], 'healthy')
    def test_missing_heartbeat_requests_cloud_recovery(self):
        self.assertEqual(recovery_plan([], self.health(90), NOW, POLICY)['action'], 'dispatch')
    def test_recent_running_or_queued_job_is_not_duplicated(self):
        for status in ['queued','in_progress']:
            runs=[{'id':1,'created_at':ago(5),'status':status}]
            self.assertEqual(recovery_plan(runs,self.health(90),NOW,POLICY)['action'],'wait')
    def test_failed_run_waits_then_retries(self):
        runs=[{'id':1,'created_at':ago(20),'status':'completed','conclusion':'failure'}]
        self.assertEqual(recovery_plan(runs,self.health(),NOW,POLICY)['action'],'dispatch')
        runs[0]['created_at']=ago(2)
        self.assertEqual(recovery_plan(runs,self.health(),NOW,POLICY)['action'],'wait')
    def test_stuck_job_can_be_cancelled_and_restarted(self):
        runs=[{'id':9,'created_at':ago(90),'status':'queued'}]
        plan=recovery_plan(runs,self.health(90),NOW,POLICY)
        self.assertEqual(plan['action'],'dispatch');self.assertEqual(plan['cancelRunIds'],[9])
    def test_local_check_is_not_a_real_cloud_heartbeat(self):
        h=self.health();h['provider']='local_verification'
        self.assertEqual(recovery_plan([],h,NOW,POLICY)['action'],'dispatch')


class PublicDiscoveryTests(unittest.TestCase):
    def data(self):
        return {'tracking':{'startedAt':'2026-10-20T00:00:00Z','excludedPostIds':{'youtube':['excluded123']}},'videos':[]}
    def feed(self, owner=CHANNEL, video='abcdefghijk', published='2026-10-20T10:00:00Z', views='42'):
        return f'''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/"><yt:channelId>{owner[2:]}</yt:channelId><link rel="alternate" href="https://www.youtube.com/channel/{owner}"/><entry><yt:videoId>{video}</yt:videoId><yt:channelId>{owner}</yt:channelId><title>A real upload</title><published>{published}</published><link rel="alternate" href="https://www.youtube.com/watch?v={video}"/><media:group><media:community><media:statistics views="{views}"/></media:community></media:group></entry></feed>'''
    def test_correct_feed_adds_public_video_with_no_guessed_cross_platform_links(self):
        data=self.data();added=discover_youtube(data,ACCOUNT,lambda _:self.feed(),setmetric)
        self.assertEqual(added,1);video=data['videos'][0]
        self.assertIsNone(video['assetUrl']);self.assertEqual(list(video['posts']),['youtube'])
        self.assertEqual(video['posts']['youtube']['metrics']['views']['value'],42)
        self.assertEqual(discover_youtube(data,ACCOUNT,lambda _:self.feed(),setmetric),0)
    def test_wrong_owner_is_rejected(self):
        with self.assertRaises(ValueError):discover_youtube(self.data(),ACCOUNT,lambda _:self.feed(owner='UCgHxdk2zTRXwsoCrICSwiRg'),setmetric)
    def test_legacy_or_excluded_video_is_not_adopted(self):
        for feed in [self.feed(published='2020-01-01T00:00:00Z'),self.feed(video='excluded123')]:
            data=self.data();self.assertEqual(discover_youtube(data,ACCOUNT,lambda _:feed,setmetric),0);self.assertEqual(data['videos'],[])
    def test_missing_view_count_keeps_previous_value_and_actual_zero_is_valid(self):
        data=self.data();discover_youtube(data,ACCOUNT,lambda _:self.feed(),setmetric)
        discover_youtube(data,ACCOUNT,lambda _:self.feed(views='unknown'),setmetric)
        self.assertEqual(data['videos'][0]['posts']['youtube']['metrics']['views']['value'],42)
        discover_youtube(data,ACCOUNT,lambda _:self.feed(views='0'),setmetric)
        self.assertEqual(data['videos'][0]['posts']['youtube']['metrics']['views']['value'],0)


if __name__=='__main__': unittest.main()
