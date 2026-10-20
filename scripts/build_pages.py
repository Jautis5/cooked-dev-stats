"""Build the independent public site, bundling the latest valid fallback feeds."""
import json, pathlib, shutil
ROOT = pathlib.Path(__file__).resolve().parents[1]
out = ROOT / '_site'
if out.exists():
    shutil.rmtree(out)
shutil.copytree(ROOT / 'site', out)
config = json.loads((out / 'data/channels.json').read_text())
feeds = {c['id']: c['dataPath'] for c in json.loads((ROOT / 'data/channels.json').read_text())['channels']}
for channel in config['channels']:
    path = out / channel['fallbackUrl']
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / feeds[channel['id']], path)
if (ROOT / 'data/health.json').exists():
    shutil.copyfile(ROOT / 'data/health.json', out / 'data/health.json')
(out / '.nojekyll').write_text('')
print('Built independent site with current public fallback snapshots.')
