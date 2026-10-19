import copy, importlib.util, pathlib, unittest
p=pathlib.Path(__file__).with_name('collect.py');spec=importlib.util.spec_from_file_location('collector',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def metric(n,at,approx=False):return {'value':n,'at':at,'approximate':approx}
def fixture():
 old='2026-10-18T14:00:00+00:00';now='2026-10-19T14:00:00+00:00'
 base={'attemptAt':old,'accounts':[{'id':'instagram','metrics':{'followers':metric(10,old)}}],
       'videos':[{'posts':{'instagram':{'id':'real-id','metrics':{'views':metric(100,old),'likes':metric(5,old)}}}}]}
 data={'lastAttemptAt':now,'accounts':[{'id':'instagram','metrics':{'followers':metric(15,now)}}],
       'videos':[{'publishedAt':'2026-10-17T14:00:00+00:00','posts':{'instagram':{'id':'real-id','metrics':{'views':metric(130,now),'likes':metric(8,now)}}}}]}
 return data,base
class ChangesTests(unittest.TestCase):
 def test_real_daily_observations(self):
  d,b=fixture();m.update_changes(d,[b]);self.assertEqual(d['changes24h']['views']['value'],30);self.assertEqual(d['changes24h']['likes']['value'],3);self.assertEqual(d['changes24h']['followers']['value'],5)
 def test_same_day_is_not_extrapolated(self):
  d,b=fixture();b['attemptAt']=d['lastAttemptAt'];m.update_changes(d,[b]);self.assertIsNone(d['changes24h']['views']);self.assertIsNone(d['changes24h']['baselineAt'])
 def test_preserved_stale_metric_is_not_zero_growth(self):
  d,b=fixture();d['videos'][0]['posts']['instagram']['metrics']['views']=copy.deepcopy(b['videos'][0]['posts']['instagram']['metrics']['views']);m.update_changes(d,[b]);self.assertIsNone(d['changes24h']['views'])
 def test_missing_and_unmatched_old_publication_prevent_comparison(self):
  d,b=fixture();del d['videos'][0]['posts']['instagram']['metrics']['likes'];m.update_changes(d,[b]);self.assertIsNone(d['changes24h']['likes'])
  d['videos'][0]['posts']['instagram']['id']='different-id';m.update_changes(d,[b]);self.assertIsNone(d['changes24h']['views'])
 def test_new_publication_counts_only_if_published_after_baseline(self):
  d,b=fixture();v=copy.deepcopy(d['videos'][0]);v['posts']['instagram']['id']='new-id';v['publishedAt']='2026-10-19T12:00:00+00:00';v['posts']['instagram']['metrics']['views']['approximate']=True;d['videos'].append(v);m.update_changes(d,[b]);self.assertEqual(d['changes24h']['views']['value'],160);self.assertTrue(d['changes24h']['views']['approximate'])
if __name__=='__main__':unittest.main()
