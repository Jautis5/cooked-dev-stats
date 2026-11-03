import copy,datetime,unittest
from unittest.mock import patch
import collect
class ObservationTime(unittest.TestCase):
 def test_observation_is_not_cycle_start(self):
  before=datetime.datetime.now(datetime.timezone.utc)
  with patch.object(collect,'NOW','2000-01-01T00:00:00+00:00'):
   p={};collect.setmetric(p,'views',123,'https://example.test/video',True)
   m=p['metrics']['views'];at=datetime.datetime.fromisoformat(m['at'])
   self.assertGreaterEqual(at,before);self.assertLessEqual(at,datetime.datetime.now(datetime.timezone.utc));self.assertNotEqual(m['at'],collect.NOW);self.assertTrue(collect.is_current(m));self.assertTrue(m['approximate'])
 def test_missing_preserves_independent_dates(self):
  old={'value':8,'at':'2026-10-01T00:00:00Z','source':'https://original.test/video','approximate':False};p={'metrics':{'views':copy.deepcopy(old)}}
  with patch.object(collect,'NOW','2026-11-03T10:30:00Z'):
   collect.setmetric(p,'views',None,'https://other.test/video');collect.setmetric(p,'likes',0,'https://public.test/video')
   self.assertEqual(p['metrics']['views'],old);self.assertFalse(collect.is_current(p['metrics']['views']));self.assertTrue(collect.is_current(p['metrics']['likes']));self.assertEqual(p['metrics']['likes']['value'],0)
  with patch.object(collect,'NOW','2026-11-03T10:45:00Z'):self.assertFalse(collect.is_current(p['metrics']['likes']))
 def test_explicit_time(self):
  p={};at='2026-11-03T10:31:12.345678+00:00';collect.setmetric(p,'views',2,'https://public.test/video',observed_at=at);self.assertEqual(p['metrics']['views']['at'],at)
 def test_naive_time_rejected(self):
  p={}
  with self.assertRaises(ValueError):collect.setmetric(p,'views',2,'https://public.test/video',observed_at='2026-11-03T10:31:12')
  self.assertEqual(p,{})
