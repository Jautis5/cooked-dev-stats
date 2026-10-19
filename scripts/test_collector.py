import importlib.util, pathlib, unittest, tempfile, json
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
if __name__=='__main__':unittest.main()
