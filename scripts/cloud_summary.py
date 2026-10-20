import json, os, pathlib
path = pathlib.Path(__file__).resolve().parents[1] / 'data/health.json'
if path.exists():
    h = json.loads(path.read_text())
    lines = ['## Social Stats cloud collection', '', 'Runs independently of Codex and the owner computer.', '', '| Channel | Run | Metrics updated |', '| --- | --- | --- |']
    lines += ['| ' + channel + ' | ' + item['status'] + ' | ' + str(item['metricsUpdated']) + ' |' for channel, item in h['channels'].items()]
    lines += ['', 'Unavailable sources preserve their last real observation times. Facebook and X require account API authorization for unattended metrics.']
    text = '\n'.join(lines) + '\n'
    print(text)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
            f.write(text)
