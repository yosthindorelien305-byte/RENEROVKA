import json, re

with open('site/data.json', 'r', encoding='utf-8') as f:
    flexa = json.load(f)

with open('site/fitify/data/catalog.json', 'r', encoding='utf-8') as f:
    fitify = json.load(f)

print(f"Flexa exercises: {len(flexa['exercises'])}, Fitify exercises: {len(fitify)}")

def normalize(s):
    if not s: return ''
    s = s.lower()
    s = re.sub(r'[\(\)\-\,\.\!\?]', ' ', s)
    return ' '.join(s.split())

# Common synonym mappings
synonyms = {
    'приседания': ['squats', 'squat', 'приседания'],
    'отжимания': ['pushups', 'push up', 'pushup', 'push-ups', 'отжимания'],
    'планка': ['plank', 'планка'],
    'выпады': ['lunges', 'lunge', 'выпады'],
    'альпинист': ['mountain climbers', 'альпинист', 'mountain climber'],
    'скручивания': ['crunches', 'crunch', 'скручивания'],
    'подъем ног': ['leg raises', 'leg raise', 'подъем ног', 'поднятие ровных ног'],
    'берпи': ['burpees', 'burpee', 'берпи'],
    'джампинг джек': ['jumping jacks', 'прыжки ноги вместе'],
    'мостик': ['bridge', 'мостик'],
    'пистолетик': ['pistol squat', 'пистолетик', 'на одной ноге'],
    'сумо': ['sumo squat', 'сумо'],
    'икры': ['calf raises', 'подъем на носки', 'икры'],
    'велосипед': ['bicycle crunch', 'велосипед'],
    'ножницы': ['scissors', 'flutter kicks', 'ножницы'],
    'лодочка': ['superman', 'лодочка', 'гиперэкстензия']
}

matches = {}

for fe in flexa['exercises']:
    eid = str(fe['id'])
    ru = normalize(fe['n'].get('ru', ''))
    en = normalize(fe['n'].get('en', ''))
    
    best_item = None
    best_score = 0
    
    for fi in fitify:
        fi_title = normalize(fi['title'])
        fi_ru = normalize(fi.get('title_ru', ''))
        
        score = 0
        if en and fi_title:
            if en == fi_title: score = 100
            elif en in fi_title or fi_title in en: score = 80
        if ru and fi_ru:
            if ru == fi_ru: score = max(score, 95)
            elif ru in fi_ru or fi_ru in ru: score = max(score, 75)
            
        # Check synonyms
        for k, syn_list in synonyms.items():
            in_fe = any(s in ru or s in en for s in syn_list)
            in_fi = any(s in fi_ru or s in fi_title for s in syn_list)
            if in_fe and in_fi:
                score = max(score, 70)
                
        if score > best_score:
            best_score = score
            best_item = fi
            
    if best_item and best_score >= 70:
        matches[eid] = {
            'video': best_item['video'],
            'audio': best_item['audio'],
            'thumbnail': best_item['thumbnail'],
            'fitify_code': best_item['code'],
            'fitify_title': best_item['title'],
            'score': best_score
        }

print(f"Matched {len(matches)} Flexa exercises with Fitify 3D videos!")

with open('site/fitify_exercise_map.json', 'w', encoding='utf-8') as f:
    json.dump(matches, f, ensure_ascii=False, indent=2)

# Print first 20 matches
for eid in sorted(matches.keys(), key=lambda x: int(x))[:20]:
    fe = next(x for x in flexa['exercises'] if str(x['id']) == eid)
    m = matches[eid]
    print(f"[{eid}] {fe['n']['ru']} ({fe['n']['en']}) -> {m['fitify_title']} ({m['video']}) [score: {m['score']}]")
