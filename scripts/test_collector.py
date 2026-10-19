import importlib.util, pathlib, unittest
from unittest.mock import patch
p=pathlib.Path(__file__).with_name('collect.py');s=importlib.util.spec_from_file_location('collector',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class CollectorTests(unittest.TestCase):
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
