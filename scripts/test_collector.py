import importlib.util, pathlib, unittest, tempfile, json, csv
from unittest.mock import patch
p=pathlib.Path(__file__).with_name('collect.py');s=importlib.util.spec_from_file_location('collector',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class CollectorTests(unittest.TestCase):
 def test_archive_keeps_original_metric_timestamp_and_is_idempotent(self):
  data={'lastAttemptAt':'2026-10-19T13:00:00+00:00','accounts':[],
   'videos':[{'id':'v1','number':1,'assetUrl':'https://drive.google.com/file/d/example/view','posts':{'instagram':{'id':'v1','url':'https://www.instagram.com/reel/v1/','metrics':{'views':{'value':17,'at':'2026-09-01T00:00:00+00:00'}}}}}]}
  with tempfile.TemporaryDirectory() as folder,patch.object(m,'ROOT',pathlib.Path(folder)):
   m.archive(data);m.archive(data)
   lines=(pathlib.Path(folder)/'data/archive/2026-10.jsonl').read_text().splitlines()
   self.assertEqual(len(lines),1)
   self.assertEqual(json.loads(lines[0])['videos'][0]['posts']['instagram']['metrics']['views']['at'],'2026-09-01T00:00:00+00:00')
 def test_missing_value_preserves_prior_observation(self):
  p={'metrics':{'views':{'value':17,'at':'earlier'}}};m.setmetric(p,'views',None,'https://example.com');self.assertEqual(p['metrics']['views'],{'value':17,'at':'earlier'})
 def test_zero_is_a_valid_observation(self):
  p={'metrics':{}};m.setmetric(p,'comments',0,'https://example.com');self.assertEqual(p['metrics']['comments']['value'],0)
 def test_negative_and_boolean_are_not_metrics(self):
  self.assertIsNone(m.num(-1));self.assertIsNone(m.num(True))
 def test_wrong_video_is_rejected_before_mutation(self):
  p={'id':'right','url':'https://www.tiktok.com/@cooked_dev_/video/right','metrics':{}}
  h='<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">{"__DEFAULT_SCOPE__":{"webapp.video-detail":{"itemInfo":{"itemStruct":{"id":"wrong","stats":{"playCount":77}}}}}}</script>'
  with patch.object(m,'request',return_value=h):
   with self.assertRaises(ValueError):m.tiktok_video(p)
  self.assertEqual(p['metrics'],{})
 def test_per_metric_export_keeps_dates_zero_and_gaps(self):
  data={'channelId':'test','accounts':[{'id':'x','name':'X','url':'https://x.com/test','status':'partial','metrics':{}}],
   'videos':[{'number':1,'title':'A','posts':{'x':{'url':'https://x.com/test/status/1','metrics':{'views':{'value':10,'at':'2026-10-20T00:00:00Z','source':'https://x.com/test/status/1'},'likes':{'value':0,'at':'2026-10-22T00:00:00Z','source':'https://x.com/test/status/1'},'saves':{'value':2,'at':'2026-10-21T00:00:00Z'}}}}}]}
  with tempfile.TemporaryDirectory() as folder:
   m.exports(data,folder)
   with open(pathlib.Path(folder)/'metrics.csv') as f:rows=list(csv.DictReader(f))
  rows={r['Metric']:r for r in rows if r['Entity']=='video'}
  self.assertEqual(rows['views']['Observed at'],'2026-10-20T00:00:00Z')
  self.assertEqual(rows['likes']['Value'],'0');self.assertEqual(rows['likes']['State'],'observed')
  self.assertEqual(rows['shares']['Value'],'');self.assertEqual(rows['shares']['State'],'not_observed')
  self.assertEqual(rows['saves']['Value'],'2')
 def test_likes_refresh_does_not_count_as_views_refresh(self):
  from refresh_all import metric_health
  at='2026-10-22T00:00:00Z'
  data={'accounts':[{'id':'x','name':'X','status':'partial'}],'videos':[{'posts':{'x':{'metrics':{'views':{'value':10,'at':'2026-10-20T00:00:00Z'},'likes':{'value':0,'at':at}}}}}]}
  health=metric_health(data,at)['x']['metricCoverage']
  self.assertEqual(health['views']['updated'],0);self.assertEqual(health['likes']['updated'],1)
  self.assertEqual(health['shares']['missing'],1)
if __name__=='__main__':unittest.main()
