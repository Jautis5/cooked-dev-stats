import copy, unittest
from unittest.mock import patch
import collect as base
import collect_channels
import official_broker
from public_fallbacks import refresh_fallbacks
from inventory_health import inventory_health
from refresh_all import metric_health

class RetiredAccountTests(unittest.TestCase):
    def fixture(self):
        at='2026-11-04T16:24:17Z'
        a={'id':'tiktok','name':'TikTok','url':'https://www.tiktok.com/@click_theory','expectedHandle':'click_theory','status':'unavailable','metrics':{}}
        p={'id':'7704295685822188822','url':a['url']+'/video/7704295685822188822','metrics':{'views':{'value':7,'at':at,'source':a['url']+'/video/7704295685822188822'}}}
        d={'channelId':'click-theory','accounts':[a],'videos':[{'id':'v1','number':1,'posts':{'tiktok':p}}]}
        c={'retiredAccounts':[{'id':'tiktok','url':a['url'],'reason':'owner_deleted','reportedAt':'2026-11-05T09:53:54Z'}]}
        return d,c
    def test_retired_identity_makes_no_public_or_official_requests(self):
        d,c=self.fixture();original=copy.deepcopy(d['videos'])
        base.apply_account_policy(d,c)
        with patch.object(base,'request') as public, patch.object(official_broker,'request') as official, patch.dict('os.environ',{'SOCIAL_STATS_BROKER_URL':'configured','SOCIAL_STATS_BROKER_KEY':'configured'}):
            refresh_fallbacks(d);collect_channels.refresh(d);official_broker.refresh(d)
            public.assert_not_called();official.assert_not_called()
        self.assertEqual(d['videos'],original)
        self.assertEqual(d['accounts'][0]['status'],'retired')
        self.assertNotIn('lastAttemptAt',d['accounts'][0])
        h=metric_health(d,base.NOW)['tiktok']
        self.assertEqual(h['access'],'inactive');self.assertEqual(h['metricsUpdated'],0)
        self.assertFalse(h['inventoryAudit']['overdue']);self.assertFalse(h['inventoryComplete'])
    def test_policy_never_disables_a_different_account(self):
        d,c=self.fixture();c['retiredAccounts'][0]['url']='https://www.tiktok.com/@replacement'
        with self.assertRaisesRegex(ValueError,'identity'):base.apply_account_policy(d,c)
        self.assertNotIn('collection',d['accounts'][0])
    def test_active_instagram_stays_active(self):
        d,c=self.fixture();ig={'id':'instagram','url':'https://www.instagram.com/click_theoory/','metrics':{}}
        d['accounts'].append(ig);base.apply_account_policy(d,c)
        self.assertTrue(base.is_active(ig));self.assertNotIn('collection',ig)
    def test_archived_full_check_is_not_renewed(self):
        d,c=self.fixture();d['discovery']={'tiktok':{'lastCompleteAt':'2026-10-28T21:18:30Z'}}
        base.apply_account_policy(d,c)
        h=inventory_health(d,d['accounts'][0],base.NOW)
        self.assertEqual(h['lastVerifiedAt'],'2026-10-28T21:18:30Z');self.assertEqual(h['state'],'retired')
        self.assertFalse(h['overdue'])

if __name__=='__main__':unittest.main()
