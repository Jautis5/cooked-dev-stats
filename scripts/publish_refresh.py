"""Publish collected snapshots safely despite simultaneous browser/manual updates.

Only a disposable detached worktree is reset. The calling checkout is preserved.
No force push; freshest measured values and remote source edits always survive.
"""
import copy, json, os, pathlib, subprocess, tempfile, time
import collect as base
from snapshot_merge import merge_snapshot, timestamp, validate
from publications import reconcile
ROOT = pathlib.Path(__file__).resolve().parents[1]


def git(root, *args, check=True):
    return subprocess.run(['git', '-C', str(root), *args], text=True, capture_output=True, check=check)


def json_at(root, ref, path):
    result = git(root, 'show', ref + ':' + path, check=False)
    return json.loads(result.stdout) if result.returncode == 0 else None


def publish(root=ROOT, before_push=None, retries=4):
    config = json.loads((root / 'data/channels.json').read_text())['channels']
    collected = {c['dataPath']: json.loads((root / c['dataPath']).read_text()) for c in config}
    baseline = {path: json_at(root, 'HEAD', path) for path in collected}
    archives = {str(p.relative_to(root)): p.read_text() for p in (root / 'data').rglob('*.jsonl')}
    health = json.loads((root / 'data/health.json').read_text()) if (root / 'data/health.json').exists() else None
    for candidate in collected.values():
        validate(candidate)
    for attempt in range(retries):
        git(root, 'fetch', '--no-tags', 'origin', 'main')
        remote_head = git(root, 'rev-parse', 'FETCH_HEAD').stdout.strip()
        with tempfile.TemporaryDirectory(prefix='social-stats-publish-') as temp:
            checkout = pathlib.Path(temp) / 'publisher'
            git(root, 'worktree', 'add', '--detach', str(checkout), remote_head)
            try:
                allowed = {c['dataPath'] for c in json.loads((checkout / 'data/channels.json').read_text())['channels']}
                ledger_path = checkout / 'data/publications.json'
                ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else None
                for relative, content in archives.items():
                    path = checkout / relative
                    if not path.is_relative_to(checkout / 'data'):
                        raise ValueError('Unsafe archive path')
                    frames = {}
                    for line in (content + '\n' + (path.read_text() if path.exists() else '')).splitlines():
                        if line.strip():
                            frame = json.loads(line)
                            frames[frame['attemptAt']] = frame
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(''.join(json.dumps(frame, ensure_ascii=False, separators=(',', ':')) + '\n' for frame in sorted(frames.values(), key=lambda f: timestamp(f['attemptAt']))))
                for relative, candidate in collected.items():
                    if relative not in allowed:
                        continue
                    path = checkout / relative
                    remote = json.loads(path.read_text())
                    incoming = copy.deepcopy(candidate)
                    # A verified post may have moved from a discovery row to its
                    # original video. Align both snapshots before deduplication
                    # so observations on that post are still merged by time.
                    if ledger is not None:
                        reconcile(remote, ledger)
                        reconcile(incoming, ledger)
                    data = merge_snapshot(remote, incoming, baseline[relative])
                    if ledger is not None: reconcile(data, ledger)
                    validate(data)
                    base.update_changes(data, directory=path.parent)
                    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
                    base.exports(data, path.parent)
                if health:
                    path = checkout / 'data/health.json'
                    prior = json.loads(path.read_text()) if path.exists() else {}
                    if timestamp(health.get('completedAt')) > timestamp(prior.get('completedAt')):
                        path.write_text(json.dumps(health, ensure_ascii=False, indent=2) + '\n')
                git(checkout, 'add', '--', 'data')
                if git(checkout, 'diff', '--cached', '--quiet', check=False).returncode == 0:
                    return remote_head
                git(checkout, '-c', 'user.name=Social Stats Cloud', '-c', 'user.email=stats@users.noreply.github.com', 'commit', '-m', 'Refresh public social metrics')
                if before_push:
                    before_push(attempt)
                pushed = git(checkout, 'push', 'origin', 'HEAD:refs/heads/main', check=False)
                if pushed.returncode == 0:
                    return git(checkout, 'rev-parse', 'HEAD').stdout.strip()
                git(root, 'fetch', '--no-tags', 'origin', 'main')
                if git(root, 'rev-parse', 'FETCH_HEAD').stdout.strip() == remote_head:
                    raise RuntimeError('Snapshot push failed without a concurrent commit; check repository write permission.')
                print('Concurrent update detected; merging original observations with the latest source (attempt ' + str(attempt + 2) + ').')
            finally:
                git(root, 'worktree', 'remove', '--force', str(checkout), check=False)
    raise RuntimeError('Snapshot publishing still conflicted after bounded retries. Collected data is retained in the workflow artifact.')


if __name__ == '__main__':
    print(json.dumps({'publishedCommit': publish()}))
