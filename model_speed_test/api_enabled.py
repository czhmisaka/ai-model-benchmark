import json, urllib.request

with urllib.request.urlopen('http://localhost:15010/config') as r:
    d = json.load(r)

models = d.get('models', [])
cases = d.get('test_cases', [])

print('models enabled 分布:')
for m in models[:5]:
    print(' ', m['name'], '| enabled:', repr(m.get('enabled')), '| type:', type(m.get('enabled')).__name__)

print()
print('cases enabled 分布:')
for t in cases[:5]:
    print(' ', t['id'], '| enabled:', repr(t.get('enabled')), '| type:', type(t.get('enabled')).__name__)
