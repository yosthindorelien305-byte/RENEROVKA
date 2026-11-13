import xml.etree.ElementTree as ET, json, re, os, shutil, glob

ROOT = r'd:\RENEROVKA'
EX = ROOT + r'\apk_extract\res'
OUT = ROOT + r'\site'
os.makedirs(OUT + r'\img\programs', exist_ok=True)
os.makedirs(OUT + r'\img\ex', exist_ok=True)
os.makedirs(OUT + r'\audio', exist_ok=True)

def load_strings(lang):
    raw = open(ROOT + r'\decoded\advanced_strings_%s.xml' % lang, encoding='utf-8').read()
    raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', raw)
    r = ET.fromstring(raw)
    d = {}
    for sec in r:
        for e in sec:
            d[e.tag] = (e.text or '').strip()
    return d

S = {l: load_strings(l) for l in ('ru', 'en')}

def parse(name):
    raw = open(ROOT + r'\decoded\%s.xml' % name, encoding='utf-8').read()
    raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', raw)
    return ET.fromstring(raw)

exercises = []
for it in parse('exercises'):
    if it.get('is_deleted') == '1':
        continue
    i = it.get('id')
    exercises.append({
        'id': int(i),
        'eq': it.get('equipment'),
        'lvl': it.get('level'),
        'rating': round(float(it.get('rating') or 0), 1),
        'unit': it.get('unit_type'),
        'mech': it.get('mechanics_type'),
        'img': os.path.exists(EX + r'\raw\svg_norm_%s.svg' % i),
        'n': {l: S[l].get('norm_%s_title' % i, '') for l in S},
        'd': {l: S[l]['norm_%s_desc' % i] for l in S if 'norm_%s_desc' % i in S[l]},
    })

workouts = []
for it in parse('workouts'):
    if it.get('is_deleted') == '1':
        continue
    i = it.get('id')
    sets = []
    for st in it.findall('set'):
        sets.append([int(st.get('value') or 1)] + [[int(n.get('id_norm')), n.get('unit_type'), int(float(n.get('norm_value') or 0)), int(n.get('rest_after') or 0)] for n in st.findall('norm')])
    workouts.append({
        'id': int(i),
        'diff': it.get('difficulty'),
        'eq': it.get('equipment'),
        'temp': it.get('temp'),
        'rating': round(float(it.get('rating') or 0), 1),
        'rb': int(it.get('seconds_between_norm') or 0),
        'rr': int(it.get('seconds_between_round') or 0),
        'pro': it.get('is_pro') == '1',
        't': {l: S[l].get('workout_%s_title' % i, '') for l in S},
        'd': {l: S[l]['workout_%s_desc' % i] for l in S if 'workout_%s_desc' % i in S[l]},
        's': sets,
    })

programs = []
for it in parse('programs'):
    i = it.get('id')
    programs.append({
        'id': int(i),
        'days': int(it.get('days_count') or 0),
        'temp': it.get('temp'),
        'pro': it.get('is_pro') == '1',
        't': {l: S[l].get('program_%s_title' % i, '') for l in S},
        'd': {l: S[l].get('program_%s_desc' % i, '') for l in S},
    })
    for cand in (EX + r'\drawable-ru-xhdpi-v4\program_%s.jpg' % i, EX + r'\drawable-xhdpi-v4\program_%s.jpg' % i):
        if os.path.exists(cand):
            shutil.copy(cand, OUT + r'\img\programs\%s.jpg' % i)
            programs[-1]['img'] = True
            break

ranks = [{'id': int(it.get('id')), 'name': it.get('short_name'), 'w': int(it.get('weight'))} for it in parse('ranks')]

keys = re.compile(r'^(wft_eq_|wt_difficulty|wt_temp|wft_equipment_title|wft_muscle_(abs|arms|back|chest|legs|shoulders)$|pr_program|unit_)')
ui = {l: {k: v for k, v in S[l].items() if keys.match(k)} for l in S}

n = 0
for f in glob.glob(EX + r'\raw\svg_norm_*.svg'):
    shutil.copy(f, OUT + r'\img\ex'); n += 1
for f in ('countdown.mp3', 'mp3_box_bell.mp3', 'mp3_workout_completed.mp3'):
    shutil.copy(EX + r'\raw\\' + f, OUT + r'\audio')
shutil.copy(EX + r'\mipmap-xxxhdpi-v4\ic_launcher.png', OUT + r'\img\logo.png') if os.path.exists(EX + r'\mipmap-xxxhdpi-v4\ic_launcher.png') else None

data = {'exercises': exercises, 'workouts': workouts, 'programs': programs, 'ranks': ranks, 'ui': ui}
json.dump(data, open(OUT + r'\data.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(len(exercises), len(workouts), len(programs), n, os.path.getsize(OUT + r'\data.json'))
print(sum(1 for w in workouts if w['t']['en']), sum(1 for e in exercises if e['n']['ru']))
