"""Security and coverage tests for the cloud MCP bridge; no platform credentials."""
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('social_backend', Path(__file__).resolve().parents[1] / 'integrations/mcp/backend.py')
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)


class BackendTests(unittest.TestCase):
    def test_signs_full_request_and_rejects_wrong_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'private.json'
            path.write_text(json.dumps({'url': 'https://script.google.com/macros/s/test-deployment/exec', 'signingKey': 'test-only-key-with-more-than-32-characters'}))
            path.chmod(0o600)
            client = backend.Backend('instagram', path)
            class Response:
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def read(self, size):
                    return json.dumps({'ok': True, 'result': {'version': 1, 'channelId': 'cooked-dev', 'platform': 'instagram', 'owner': {'handle': 'wrong-account'}}}).encode()
            def check(request, timeout):
                body = json.loads(request.data)
                expected = hmac.new(b'test-only-key-with-more-than-32-characters', body['message'].encode(), hashlib.sha256).hexdigest()
                self.assertEqual(body['signature'], expected)
                self.assertEqual(json.loads(body['message'])[4:], ['cooked-dev', 'instagram', {}])
                self.assertEqual(timeout, 45)
                return Response()
            with patch.object(backend.urllib.request, 'urlopen', side_effect=check):
                with self.assertRaisesRegex(backend.BackendError, '^IDENTITY_MISMATCH$'):
                    client.call('cooked-dev', 'capabilities')
            path.chmod(0o644)
            with self.assertRaisesRegex(backend.BackendError, '^CONFIGURATION_REQUIRED$'):
                client.call('cooked-dev', 'capabilities')

    def test_scan_visits_replies_deduplicates_and_resumes(self):
        client = backend.Backend('tiktok')
        client._continuation_key = b'test-only-state-signing-key'
        def page(channel, post, cursor='', limit=100):
            pages = {
                '': {'comments': [{'id': '1', 'text': 'A', 'replyCursor': 'reply-1'}], 'nextCursor': 'top-2'},
                'top-2': {'comments': [{'id': '1', 'text': 'A duplicate', 'replyCursor': 'reply-1'}, {'id': '2', 'text': 'B', 'replyCursor': None}], 'nextCursor': None},
                'reply-1': {'comments': [{'id': '3', 'text': 'Reply', 'replyCursor': None}], 'nextCursor': None},
            }
            return pages[cursor] | {'checkedAt': '2026-10-22T10:00:00Z', 'scope': 'api_accessible'}
        client.comments = page
        first = client.scan_comments('cooked-dev', '123', max_pages=1)
        self.assertFalse(first['complete'])
        self.assertEqual(len(first['comments']), 1)
        second = client.scan_comments('cooked-dev', '123', continuation=first['continuation'])
        self.assertTrue(second['complete'])
        self.assertEqual([r['id'] for r in second['comments']], ['2', '3'])
        self.assertEqual(second['uniqueCommentsAcrossScan'], 3)
        with self.assertRaisesRegex(backend.BackendError, '^INVALID_REQUEST$'):
            client.scan_comments('indian-builds', '123', continuation=first['continuation'])
        altered = json.loads(first['continuation'])
        altered['state'] = altered['state'].replace('top-2', 'fake-cursor')
        with self.assertRaisesRegex(backend.BackendError, '^INVALID_REQUEST$'):
            client.scan_comments('cooked-dev', '123', continuation=json.dumps(altered))

    def test_failed_or_malformed_page_never_becomes_complete_empty(self):
        client = backend.Backend('instagram')
        client._continuation_key = b'test-only-state-signing-key'
        def fail(*args): raise backend.BackendError('CONFIGURATION_REQUIRED')
        client.comments = fail
        first = client.scan_comments('cooked-dev', '123')
        self.assertFalse(first['complete'])
        self.assertEqual(first['error'], 'CONFIGURATION_REQUIRED')
        self.assertEqual(json.loads(json.loads(first['continuation'])['state'])['pending'], [''])
        client.comments = lambda *args: {'comments': [{'id': '2', 'text': 'B'}]}
        second = client.scan_comments('cooked-dev', '123', continuation=first['continuation'])
        self.assertFalse(second['complete'])
        self.assertEqual(second['error'], 'SOURCE_UNAVAILABLE')

    def test_http_failure_is_sanitized(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'private.json'
            path.write_text(json.dumps({'url': 'https://script.google.com/macros/s/test/exec', 'signingKey': 'a' * 64}))
            path.chmod(0o600)
            client = backend.Backend('instagram', path)
            with patch.object(backend.urllib.request, 'urlopen', side_effect=RuntimeError('https://private?access_token=NEVER-SURFACE')):
                with self.assertRaisesRegex(backend.BackendError, '^SOURCE_UNAVAILABLE$'):
                    client.call('cooked-dev', 'capabilities')

    def test_archived_history_preserves_observation_dates_and_deduplicates_retries(self):
        client = backend.Backend('instagram')
        def record(at, value):
            return {'attemptAt': '2026-10-22T10:00:00Z', 'accounts': [{'id': 'instagram', 'metrics': {
                'followers': {'at': at, 'value': value, 'source': 'https://www.instagram.com/cooked_dev/'}}}]}
        data = [record('2026-10-22T11:00:00+03:00', 5), record('2026-10-22T08:30:00Z', 6), record('2026-10-22T11:00:00+03:00', 5)]
        client._public_feed = lambda *args: ('\n'.join(json.dumps(r) for r in data), 'fixed-public-source')
        result = client.metric_history('cooked-dev', '2026-10', 'followers')
        self.assertEqual([r['value'] for r in result['observations']], [5, 6])
        self.assertEqual(result['observations'][0]['at'], '2026-10-22T11:00:00+03:00')


if __name__ == '__main__':
    unittest.main()
