import json, pathlib
d=json.loads((pathlib.Path(__file__).resolve().parents[1]/'data/latest.json').read_text())
assert len(d['accounts'])==5
ids=[v['id'] for v in d['videos']];assert len(ids)==len(set(ids))
urls=[]
for v in d['videos']:
 for platform,p in v['posts'].items():
  assert p['url'].startswith('https://')
  urls.append(p['url'])
  for m in p.get('metrics',{}).values():
   assert isinstance(m['value'],int) and m['value']>=0
   assert m['at'] and m['source']==p['url']
assert len(urls)==len(set(urls))
assert all(a['status'] in ['snapshot','ok','partial','unavailable'] for a in d['accounts'])
print('Verified',len(ids),'videos and',len(urls),'publications. Missing metrics stay missing.')
