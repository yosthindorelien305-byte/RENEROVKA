import re
p = r'd:\RENEROVKA\site\app.js'
L = open(p, encoding='utf-8').read().split('\n')
# 1-indexed line numbers from grep
def rng(a, b): return list(range(a - 1, b))
drop = set()
drop.update(rng(79, 84))            # program edit branch
drop.update(rng(172, 199))          # after(): edit handlers (replaced below)
drop.update(rng(243, 292))          # workout editor function
drop.update({99 + 0})               # placeholder (no-op, replaced below)
drop.discard(98)
drop.update(rng(100, 101))          # workout edit branch
drop.add(111)                       # btnrow (0-index of line 112)
out = []
for i, l in enumerate(L):
    if i in drop:
        if i == 171:
            out.append("    if (name == 'workout') { const w = woMap[arg]; if (w) document.getElementById('go').onclick = () => play(w); }")
        continue
    out.append(l)
s = '\n'.join(out)
s = s.replace("<p><button class=\"btn alt\" id=\"pe-edit\">✏️ ${L == 'ru' ? 'Изменить' : 'Edit'}</button></p>", '')
s = s.replace("<p><button class=\"btn\" id=\"w-new\">＋ ${L == 'ru' ? 'Создать свою тренировку' : 'Create workout'}</button></p>", '')
s = s.replace('src="img/programs/${p.id}.jpg" style="width:100%', 'src="${pImg(p)}" style="width:100%')
s = re.sub(r'src="img/programs/\$\{p\.id\}\.jpg"', 'src="${pImg(p)}"', s)
s = s.replace('--hero:url(img/programs/${hp.id}.jpg)', '--hero:url(${pImg(hp)})')
s = s.replace("let arg = null, mode = null;", "let arg = null;").replace("arg = a; mode = b;", "arg = a;")
s = s.replace("const [, name = 'home', a, b] =", "const [, name = 'home', a] =")
open(p, 'w', encoding='utf-8', newline='').write(s)
print(len(s.split('\n')))
