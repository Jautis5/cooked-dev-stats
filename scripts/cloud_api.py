"""Repository-scoped GitHub access using only the job's temporary token."""
import base64, json, re, time, urllib.error, urllib.request


class CloudAPI:
    def __init__(self, repository, token):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
            raise ValueError('Invalid repository identity')
        self.repository, self.token = repository, token

    def call(self, path, body=None):
        if (path and not path.startswith('/')) or '://' in path:
            raise ValueError('Repository-relative API path required')
        for attempt in range(3):
            request = urllib.request.Request('https://api.github.com/repos/' + self.repository + path,
                data=json.dumps(body).encode() if body is not None else None,
                headers={'Authorization':'Bearer '+self.token, 'Accept':'application/vnd.github+json',
                         'Content-Type':'application/json', 'User-Agent':'Social-Stats-Cloud',
                         'X-GitHub-Api-Version':'2022-11-28'})
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    raw = response.read()
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as error:
                if body is not None or error.code not in [429, 500, 502, 503, 504] or attempt == 2:
                    raise
            except (urllib.error.URLError, TimeoutError):
                if body is not None or attempt == 2:
                    raise
            time.sleep(2 ** (attempt + 1))

    def file(self, path):
        if not re.fullmatch(r'[A-Za-z0-9_./-]+', path) or '..' in path:
            raise ValueError('Unsafe file path')
        result = self.call('/contents/' + path + '?ref=main')
        return json.loads(base64.b64decode(result['content']))
