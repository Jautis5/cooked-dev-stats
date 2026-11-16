import importlib.util, pathlib, unittest, tempfile, json, csv
from unittest.mock import patch, MagicMock
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
class YoutubePublicMetricsTests(unittest.TestCase):
 def fixture(self,title='11',label='like this video along with 11 other people',owner='channel',video='video',player=None):
  button={'buttonViewModel':{'iconName':'LIKE','title':title,'accessibilityText':label}}
  toggle={'defaultButtonViewModel':button,'toggledButtonViewModel':{'buttonViewModel':{'iconName':'LIKE','title':'999999'}}}
  actions={'segmentedLikeDislikeButtonViewModel':{'likeButtonViewModel':{'likeButtonViewModel':{'toggleButtonViewModel':{'toggleButtonViewModel':toggle}}}}}
  sections=[{'videoPrimaryInfoRenderer':{'viewCount':{'videoViewCountRenderer':{'originalViewCount':'1256'}},'videoActions':{'menuRenderer':{'topLevelButtons':[actions]}}}}, {'videoSecondaryInfoRenderer':{'owner':{'videoOwnerRenderer':{'navigationEndpoint':{'browseEndpoint':{'browseId':owner}}}}}}]
  initial={'currentVideoEndpoint':{'watchEndpoint':{'videoId':video}},'contents':{'twoColumnWatchNextResults':{'results':{'results':{'contents':sections}}}}}
  return 'var ytInitialData = '+json.dumps(initial)+';var ytInitialPlayerResponse = '+json.dumps(player or {})+';'
 def post(self):return {'id':'video','url':'https://www.youtube.com/shorts/video','metrics':{'likes':{'value':7,'at':'earlier'}}}
 def test_current_primary_like_count_excludes_hypothetical_toggled_value(self):
  with patch.object(m,'request',return_value=self.fixture()):result=m.youtube_video(self.post(),'channel')
  self.assertEqual(result['metrics']['likes']['value'],11)
  self.assertEqual(result['metrics']['views']['value'],1256)
 def test_exact_accessible_count_overrides_rounded_button(self):
  with patch.object(m,'request',return_value=self.fixture('1.2K','like this video along with 1,234 other people')):result=m.youtube_video(self.post(),'channel')
  self.assertEqual(result['metrics']['likes']['value'],1234);self.assertFalse(result['metrics']['likes']['approximate'])
 def test_rounded_count_remains_approximate(self):
  with patch.object(m,'request',return_value=self.fixture('1.2K','Like')):result=m.youtube_video(self.post(),'channel')
  self.assertEqual(result['metrics']['likes']['value'],1200);self.assertTrue(result['metrics']['likes']['approximate'])
 def test_real_zero_and_hidden_likes_are_distinct(self):
  with patch.object(m,'request',return_value=self.fixture('0','like this video')):result=m.youtube_video(self.post(),'channel')
  self.assertEqual(result['metrics']['likes']['value'],0)
  post=self.post()
  with patch.object(m,'request',return_value=self.fixture('Like','like this video')):m.youtube_video(post,'channel')
  self.assertEqual(post['metrics']['likes'],{'value':7,'at':'earlier'})
 def test_mismatched_owner_or_video_cannot_change_any_count(self):
  for body in [self.fixture(owner='other'),self.fixture(video='other'),self.fixture(player={'videoDetails':{'videoId':'other'}})]:
   post=self.post()
   with patch.object(m,'request',return_value=body):
    with self.assertRaises(ValueError):m.youtube_video(post,'channel')
   self.assertEqual(post,self.post())
 def test_metadata_without_player_can_refresh_public_counters(self):
  # A playback login wall does not hide verified public watch-page metadata.
  with patch.object(m,'request',return_value=self.fixture(player={'playabilityStatus':{'status':'LOGIN_REQUIRED'}})):result=m.youtube_video(self.post(),'channel')
  self.assertEqual(result['metrics']['likes']['value'],11)
 def test_absent_primary_metadata_does_not_import_recommendation_likes(self):
  body=self.fixture().replace('"results": {"results":','"secondaryResults": {"results":')
  post=self.post()
  with patch.object(m,'request',return_value=body):
   with self.assertRaises(ValueError):m.youtube_video(post,'channel')
  self.assertEqual(post,self.post())

class YoutubeCommentCountTests(unittest.TestCase):
 def initial(self):
  section={'sectionIdentifier':'comment-item-section','targetId':'comments-section','contents':[{'continuationItemRenderer':{'continuationEndpoint':{'continuationCommand':{'token':'public-cursor','request':'CONTINUATION_REQUEST_TYPE_WATCH_NEXT'}}}}]}
  return {'contents':{'twoColumnWatchNextResults':{'results':{'results':{'contents':[{'itemSectionRenderer':section}]}}}}}
 def test_only_public_aggregate_is_returned_with_a_bounded_request(self):
  for label,expected in [('2',(2,False)),('0',(0,False)),('1.2K',(1200,True)),('Comments',(None,False))]:
   response=MagicMock();response.__enter__.return_value.read.return_value=json.dumps({'header':{'commentsHeaderRenderer':{'commentsCount':{'runs':[{'text':label}]}}},'comments':[{'text':'discard this text','author':'discard identity'}]}).encode()
   with patch.object(m.urllib.request,'urlopen',return_value=response) as request:
    self.assertEqual(m.youtube_comments(self.initial(),'"INNERTUBE_CLIENT_VERSION":"2.20261116"'),expected)
    self.assertEqual(request.call_args.kwargs['timeout'],8)
    req=request.call_args.args[0];self.assertEqual(req.full_url,'https://www.youtube.com/youtubei/v1/next')
    self.assertEqual(json.loads(req.data)['continuation'],'public-cursor')
 def test_recommendation_or_missing_cursors_never_trigger_a_request(self):
  for initial in [{},json.loads(json.dumps(self.initial()).replace('comments-section','recommendations'))]:
   with patch.object(m.urllib.request,'urlopen') as request:
    self.assertEqual(m.youtube_comments(initial,'"INNERTUBE_CLIENT_VERSION":"2.20261116"'),(None,False));request.assert_not_called()
 def test_unavailable_comments_preserve_prior_count_and_keep_working_likes(self):
  post=YoutubePublicMetricsTests().post();post['metrics']['comments']={'value':2,'at':'earlier'}
  with patch.object(m,'request',return_value=YoutubePublicMetricsTests().fixture()),patch.object(m,'youtube_comments',side_effect=TimeoutError):m.youtube_video(post,'channel')
  self.assertEqual(post['metrics']['comments'],{'value':2,'at':'earlier'});self.assertEqual(post['metrics']['likes']['value'],11)
 def test_wrong_owner_does_not_request_comments(self):
  with patch.object(m,'request',return_value=YoutubePublicMetricsTests().fixture(owner='other')),patch.object(m,'youtube_comments') as comments:
   with self.assertRaises(ValueError):m.youtube_video(YoutubePublicMetricsTests().post(),'channel')
   comments.assert_not_called()

if __name__=='__main__':unittest.main()
