import json
p = r'd:\RENEROVKA\server.py'
s = open(p, encoding='utf-8', newline='').read().replace('gemini-2.5-flash', 'gemini-3.8-flash')
open(p, 'w', encoding='utf-8', newline='').write(s)
p = r'd:\RENEROVKA\site\admin.js'
s = open(p, encoding='utf-8', newline='').read()
a = s.index('<datalist id="ai-models">'); b = s.index('</datalist>', a)
s = s[:a] + '<datalist id="ai-models"><option value="gemini-3.8-flash"><option value="gemini-3.8-pro">' + s[b:]
open(p, 'w', encoding='utf-8', newline='').write(s)
f = r'd:\RENEROVKA\server_data\ai.json'
c = json.load(open(f, encoding='utf-8')); print('old model:', c['model'], '| key set:', bool(c.get('key')))
c['model'] = 'gemini-3.8-flash'
json.dump(c, open(f, 'w', encoding='utf-8'), ensure_ascii=False)
