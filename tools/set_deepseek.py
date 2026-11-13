p = r'd:\RENEROVKA\site\admin.js'
s = open(p, encoding='utf-8', newline='').read()
s = s.replace("['DeepSeek', 'https://api.deepseek.com/v1', 'deepseek-chat']", "['DeepSeek', 'https://api.deepseek.com', 'deepseek-v4-flash']")
open(p, 'w', encoding='utf-8', newline='').write(s)
p = r'd:\RENEROVKA\server.py'
s = open(p, encoding='utf-8', newline='').read().replace('\r\n', '\n')
s = s.replace("    body = {'model': cfg.get('model'), 'messages': msgs, 'temperature': 0.7, 'max_tokens': 900}\n",
"    body = {'model': cfg.get('model'), 'messages': msgs, 'temperature': 0.7, 'max_tokens': 900}\n    if 'api.deepseek.com' in base:\n        body['thinking'] = {'type': 'disabled'}     # fast chat answers, no reasoning mode\n")
open(p, 'w', encoding='utf-8', newline='').write(s)
# switch saved config to DeepSeek (key is added by the owner in the admin panel)
import json
f = r'd:\RENEROVKA\server_data\ai.json'
c = json.load(open(f, encoding='utf-8'))
c.update({'provider': 'openai', 'base_url': 'https://api.deepseek.com', 'model': 'deepseek-v4-flash', 'key': ''})
json.dump(c, open(f, 'w', encoding='utf-8'), ensure_ascii=False)
print('ok')
