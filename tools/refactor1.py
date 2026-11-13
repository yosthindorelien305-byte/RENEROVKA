import re
p = r'd:\RENEROVKA\site\app.js'
s = open(p, encoding='utf-8-sig').read()
a = s.index('  const T = {')
b = s.index('  const t = k =>')
block = s[a:b]
texts = 'window.TEXTS = ' + block.strip()[len('const T = '):].rstrip(';') + ';\n'
extra = '''Object.assign(window.TEXTS.ru, { welcome: 'Добро пожаловать', potd: 'Программа дня', startShort: 'Начать', weekAct: 'Активность за неделю', quick: 'Быстрые тренировки', seeAll: 'Все', time: 'время', footer: 'Train smart. Move better.' });
Object.assign(window.TEXTS.en, { welcome: 'Welcome back', potd: 'Program of the day', startShort: 'Start', weekAct: 'Weekly activity', quick: 'Quick workouts', seeAll: 'See all', time: 'active time', footer: 'Train smart. Move better.' });
'''
open(r'd:\RENEROVKA\site\texts.js', 'w', encoding='utf-8').write(texts + extra)
s = s[:a] + '  const T = window.TEXTS;\n  ' + s[b:]
open(p, 'w', encoding='utf-8').write(s)

# css: make accent themable
c = open(r'd:\RENEROVKA\site\style.css', encoding='utf-8-sig').read()
for old, new in [('198,244,50', 'var(--acr)'), ('#e2ff55', 'var(--ac-l)'), ('#ecff7a', 'var(--ac-l)'), ('#d7ff6a', 'var(--ac-l)'), ('#a9e000', 'var(--ac-d)'), ('#b8f000', 'var(--ac-d)'), ('#a4d11a', 'var(--ac-d)'), ('168,224,0', 'var(--acr)'), ('#c6f432', '#c6f432')]:
    c = c.replace(old, new)
c = c.replace('--ac:var(--ac-l)', '--ac:#c6f432')
# restore root var definitions (the :root line had original values)
c = re.sub(r'--ac:[^;]*;--ac-d:[^;]*;', '--ac:#c6f432;--ac-l:#e2ff55;--ac-d:#a4d11a;--acr:198,244,50;', c, count=1)
c = c.replace('rgba(var(--acr),', 'rgba(var(--acr),')
open(r'd:\RENEROVKA\site\style.css', 'w', encoding='utf-8').write(c)
print(re.search(r':root\{[^}]*\}', c).group(0))
print('ok', len(texts))
