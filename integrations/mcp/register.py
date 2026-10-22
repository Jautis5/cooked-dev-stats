"""Register only these two custom MCPs; preserve every unrelated configuration."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib

root = Path(__file__).resolve().parent
config = Path.home() / '.codex/config.toml'
before_text = config.read_text()
before = tomllib.loads(before_text)
private = Path.home() / '.codex/private'
private.mkdir(mode=0o700, exist_ok=True)
backup = private / 'codex-config-before-social-backends.toml'
if not backup.exists():
    fd = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(before_text)
codex = '/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex'
for platform in ['instagram', 'tiktok']:
    name = 'social-' + platform + '-backend'
    args = [str(root / 'server.py'), '--platform', platform]
    existing = before.get('mcp_servers', {}).get(name)
    if existing and (existing.get('command') != sys.executable or existing.get('args') != args):
        raise RuntimeError('Unrelated MCP name collision: ' + name)
    if not existing:
        subprocess.run([codex, 'mcp', 'add', name, '--', sys.executable, *args], check=True)
text = config.read_text()
for platform in ['instagram', 'tiktok']:
    name = 'social-' + platform + '-backend'
    pattern = r'(\[mcp_servers\.' + re.escape(name) + r'\]\n)([\s\S]*?)(?=\n\[|\Z)'
    match = re.search(pattern, text)
    if not match:
        raise RuntimeError('MCP was not registered')
    body = match[2]
    if 'tool_timeout_sec' not in body:
        body = body.rstrip() + '\ntool_timeout_sec = 240\nstartup_timeout_sec = 15\n'
        text = text[:match.start(2)] + body + text[match.end(2):]
parsed = tomllib.loads(text)
for key, value in before.get('mcp_servers', {}).items():
    # The official CLI omits optional empty args arrays when serializing TOML.
    prior = dict(value)
    current = dict(parsed['mcp_servers'].get(key, {}))
    if prior.get('args') == []:
        prior.pop('args')
    if current.get('args') == []:
        current.pop('args')
    if key not in ['social-instagram-backend', 'social-tiktok-backend'] and current != prior:
        raise RuntimeError('Unrelated MCP configuration changed')
config.write_text(text)
os.chmod(config, 0o600)
print(json.dumps({'registered': ['social-instagram-backend', 'social-tiktok-backend'], 'secretsInConfig': False, 'otherServersPreserved': True}))
