import json, urllib.request, re, os
B = 'http://localhost:8080'
def rq(path, data=None, headers=None, method=None):
    r = urllib.request.Request(B + path, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(r) as f: return f.status, f.read()
    except urllib.error.HTTPError as e: return e.code, e.read()
print('index', rq('/')[0], 'admin', rq('/admin.html')[0], 'secret leak', rq('/../server_data/admin.json')[0], rq('/server.py')[0])
pw = open(r'd:\RENEROVKA\ADMIN_PASSWORD.txt', encoding='utf-8').read().split('\n')[1]
print('bad login', rq('/api/login', json.dumps({'password': 'x'}).encode())[0])
s, b = rq('/api/login', json.dumps({'password': pw}).encode()); tok = json.loads(b)['token']; print('login', s)
H = {'Authorization': 'Bearer ' + tok}
print('save noauth', rq('/api/save?file=config', b'{}')[0])
print('save', rq('/api/save?file=config', json.dumps({'brand': 'Flexa'}).encode(), H)[0])
print('upload bad ext', rq('/api/upload?name=a', b'x', dict(H, **{'X-Filename': 'a.exe'}))[0])
s, b = rq('/api/upload?name=test_img', b'<svg xmlns="http://www.w3.org/2000/svg"/>', dict(H, **{'X-Filename': 'a.svg'})); print('upload', s, b)
print(rq('/content/uploads/test_img.svg')[0])
os.remove(r'd:\RENEROVKA\site\content\uploads\test_img.svg'); os.remove(r'd:\RENEROVKA\site\content\config.json')
