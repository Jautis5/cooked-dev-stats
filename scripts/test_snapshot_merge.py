"""Explicit completeness corrections must not retract measurements or revive bad proof."""
import copy, unittest
from snapshot_merge import merge_discovery, merge_snapshot
from test_cloud_pipeline import fixture, metric

BAD='2026-11-03T15:24:43.937Z'
FALLBACK='2026-11-03T13:39:48.715Z'
AUDIT='2026-11-03T21:05:45.059708+00:00'
def correction(at=BAD, fallback=FALLBACK):
    return {'at':at,'recordedAt':AUDIT,'fallbackAt':fallback,'reason':'Outer document end did not verify the actual video-list terminal state.'}
def report(at=BAD):
    return {'checkedAt':at,'lastCompleteAt':at,'lastCompletePostCount':4,'complete':True,'status':'checked','method':'browser_bulk'}

class CompletenessRevocationTests(unittest.TestCase):
    def test_correction_changes_only_discovery_and_keeps_actual_source_time(self):
        remote=fixture();remote['discovery']={'tiktok':report()}
        candidate=copy.deepcopy(remote);candidate['discovery']={'tiktok':{'revokedCompleteChecks':[correction()]}}
        before=copy.deepcopy(remote);out=merge_snapshot(remote,candidate)
        self.assertEqual(remote,before)
        for key in set(out)-{'discovery'}:self.assertEqual(out[key],before[key])
        result=out['discovery']['tiktok'];self.assertEqual(result['checkedAt'],BAD);self.assertEqual(result['lastCompleteAt'],FALLBACK)
        self.assertFalse(result['complete']);self.assertEqual(result['status'],'partial');self.assertNotIn('lastCompletePostCount',result)
    def test_stale_replay_in_either_direction_does_not_resurrect_revoked_check(self):
        fixed=merge_discovery(report(),{'revokedCompleteChecks':[correction()]})
        for a,b in [(fixed,report()),(report(),fixed)]:
            result=merge_discovery(a,b);self.assertEqual(result['lastCompleteAt'],FALLBACK);self.assertFalse(result['complete']);self.assertEqual(len(result['revokedCompleteChecks']),1)
        offset=report('2026-11-03T15:24:43.937000+00:00')
        self.assertEqual(merge_discovery(fixed,offset)['lastCompleteAt'],FALLBACK)
    def test_future_partial_reports_keep_tombstone_and_newer_metrics(self):
        remote=fixture();remote['discovery']={'tiktok':merge_discovery(report(),{'revokedCompleteChecks':[correction()]})}
        incoming=copy.deepcopy(remote);incoming['discovery']={'tiktok':{'checkedAt':'2026-11-03T21:06:00Z','complete':False,'lastCompleteAt':BAD}}
        post=incoming['videos'][0]['posts']['youtube'];post['metrics']['views']=metric(99,'2026-11-03T21:06:00Z')
        out=merge_snapshot(remote,incoming);self.assertEqual(out['discovery']['tiktok']['lastCompleteAt'],FALLBACK);self.assertEqual(len(out['discovery']['tiktok']['revokedCompleteChecks']),1)
        self.assertEqual(out['videos'][0]['posts']['youtube']['metrics']['views']['value'],99)
    def test_later_legitimate_completion_and_count_survive_old_correction(self):
        legitimate=report('2026-11-03T21:04:00Z');legitimate['lastCompletePostCount']=12
        for a,b in [(legitimate,{'revokedCompleteChecks':[correction()]}),({'revokedCompleteChecks':[correction()]},legitimate)]:
            result=merge_discovery(a,b);self.assertEqual(result['lastCompleteAt'],legitimate['lastCompleteAt']);self.assertEqual(result['lastCompletePostCount'],12);self.assertTrue(result['complete'])
    def test_revocation_union_is_idempotent_and_excludes_revoked_fallbacks(self):
        first={'revokedCompleteChecks':[correction()]}
        second={'revokedCompleteChecks':[correction(FALLBACK,'2026-11-03T12:00:00Z')]}
        a=merge_discovery(first,second);b=merge_discovery(second,first)
        self.assertEqual(a,b);self.assertEqual(a['lastCompleteAt'],'2026-11-03T12:00:00Z');self.assertEqual(len(a['revokedCompleteChecks']),2)
        self.assertEqual(merge_discovery(a,a),a)
    def test_bad_revocation_rejected_without_mutating_inputs(self):
        for change in [{'fallbackAt':BAD},{'recordedAt':'2026-11-03T12:00:00Z'},{'fallbackPostCount':True},{'reason':''},{'at':'not a date'},{'privateRaw':'not allowed'}]:
            record=correction();record.update(change);remote=report();before=copy.deepcopy(remote)
            with self.subTest(change=change),self.assertRaises(ValueError):merge_discovery(remote,{'revokedCompleteChecks':[record]})
            self.assertEqual(remote,before)
    def test_equal_revocation_records_merge_counts_symmetrically_without_changing_current_counts(self):
        plain=correction();counted=dict(plain,fallbackPostCount=3)
        left={'checkedAt':'2026-11-03T21:00:00Z','lastCompleteAt':FALLBACK,'listedPosts':9,'reportedPosts':13,'revokedCompleteChecks':[plain]}
        right=copy.deepcopy(left);right['revokedCompleteChecks']=[counted]
        a=merge_discovery(left,right);b=merge_discovery(right,left)
        self.assertEqual(a,b);self.assertEqual(a['lastCompletePostCount'],3)
        self.assertEqual(a['listedPosts'],9);self.assertEqual(a['reportedPosts'],13)

if __name__=='__main__':unittest.main()
