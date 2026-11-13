import json, urllib.request
B = 'http://localhost:8080'
def rq(path, data=None, headers=None):
    r = urllib.request.Request(B + path, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(r) as f: return f.status, f.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()
print('status', rq('/api/coach/status'))
print('coach no key', rq('/api/coach', json.dumps({'messages': [{'role': 'user', 'text': 'hi'}]}).encode()))
print('settings noauth', rq('/api/ai/settings')[0])
pw = open(r'd:\RENEROVKA\ADMIN_PASSWORD.txt', encoding='utf-8').read().split('\n')[1]
tok = json.loads(rq('/api/login', json.dumps({'password': pw}).encode())[1])['token']
H = {'Authorization': 'Bearer ' + tok}
print('settings', rq('/api/ai/settings', headers=H))
import sys; sys.path.insert(0, r'd:\RENEROVKA')
import server
c = server.catalog(); print('catalog chars', len(c), c[:150].replace('\n', ' | '))
