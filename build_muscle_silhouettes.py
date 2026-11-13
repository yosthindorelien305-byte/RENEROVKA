import os, struct, re, json

SRC_DIR = 'fitify_all_extracted/vector_drawables_xml'
OUT_DIR = 'fitify_all_extracted/muscle_silhouette_svgs'
SITE_MUSCLE_DIR = 'site/fitify/muscles'

for d in [OUT_DIR, SITE_MUSCLE_DIR]:
    os.makedirs(d, exist_ok=True)

def extract_paths_from_axml(data):
    if len(data) < 40 or data[:2] != b'\x03\x00':
        return []
    header_type, header_size, chunk_size = struct.unpack('<HHI', data[8:16])
    string_count, style_count, flags, strings_start, styles_start = struct.unpack('<IIIII', data[16:36])
    is_utf8 = bool(flags & 0x100)
    indices = [struct.unpack('<I', data[36+i*4:40+i*4])[0] for i in range(string_count)]
    pool_start = 8 + strings_start
    strings = []
    for idx in indices:
        p = pool_start + idx
        if is_utf8:
            null_pos = data.find(b'\x00', p)
            while p < null_pos and data[p] < 32 and data[p] != 0: p += 1
            strings.append(data[p:null_pos].decode('utf-8', errors='ignore'))
        else:
            u16_len = struct.unpack('<H', data[p:p+2])[0]
            strings.append(data[p+2:p+2+u16_len*2].decode('utf-16le', errors='ignore'))
    
    clean_paths = []
    for s in strings:
        m = re.search(r'([Mm][0-9\.\,\s\-LlHhVvCcSsQqTtAaZz]+)', s)
        if m and len(m.group(1)) > 20:
            clean_paths.append(m.group(1).strip())
    return clean_paths

VIEWBOX = "0 0 175 330"

muscle_data = {}
for f in sorted(os.listdir(SRC_DIR)):
    if f.startswith('md_') and f.endswith('.xml') and not f.endswith('base2.xml'):
        key = f.replace('.xml', '')
        with open(os.path.join(SRC_DIR, f), 'rb') as fp:
            paths = extract_paths_from_axml(fp.read())
            muscle_data[key] = paths
            
            # Write individual SVG
            svg_content = f'''<?xml version="1.0" encoding="utf-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="{VIEWBOX}" fill="none">
  <!-- {key} -->
  <g id="{key}" fill="#00e699">
'''
            for p in paths:
                svg_content += f'    <path d="{p}" />\n'
            svg_content += '  </g>\n</svg>\n'
            
            with open(os.path.join(OUT_DIR, f'{key}.svg'), 'w', encoding='utf-8') as out_f:
                out_f.write(svg_content)
            with open(os.path.join(SITE_MUSCLE_DIR, f'{key}.svg'), 'w', encoding='utf-8') as out_f:
                out_f.write(svg_content)

print(f'Wrote {len(muscle_data)} individual muscle SVGs.')

# Now build Master Composite Front SVG
front_base_paths = muscle_data.get('md_front_base', [])
master_front_svg = f'''<?xml version="1.0" encoding="utf-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="{VIEWBOX}" class="fitify-mannequin front-mannequin">
  <defs>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="2.5" result="blur" />
      <feComposite in="SourceGraphic" in2="blur" operator="over" />
    </filter>
  </defs>
  <!-- Base Body Mannequin Front -->
  <g id="front_base" fill="#1e2e2a" stroke="#2d453f" stroke-width="0.5">
'''
for p in front_base_paths:
    master_front_svg += f'    <path d="{p}" />\n'
master_front_svg += '  </g>\n  <!-- Front Muscle Groups -->\n'

front_groups = [
    ('chest', 'md_front_chest', 'Грудь'),
    ('abs', 'md_front_abs', 'Пресс'),
    ('obliques', 'md_front_obliques', 'Косые мышцы'),
    ('biceps', 'md_front_biceps', 'Бицепсы'),
    ('quads', 'md_front_quads', 'Квадрицепсы'),
    ('shoulders_front', 'md_front_shoulders_front', 'Передние дельты'),
    ('shoulders_side', 'md_front_shoulders_side', 'Средние дельты'),
    ('forearm_anterior', 'md_front_forearm_anterior', 'Предплечья'),
    ('lats', 'md_front_lats', 'Широчайшие'),
    ('adductors', 'md_front_adductors', 'Приводящие мышцы'),
    ('neck_front', 'md_front_neck_front', 'Шея')
]

for tag, file_key, label in front_groups:
    paths = muscle_data.get(file_key, [])
    master_front_svg += f'  <g id="front_{tag}" class="muscle-layer" data-name="{label}" fill="#00e699" opacity="0.15">\n'
    for p in paths:
        master_front_svg += f'    <path d="{p}" />\n'
    master_front_svg += '  </g>\n'

master_front_svg += '</svg>\n'

with open(os.path.join(OUT_DIR, 'master_mannequin_front.svg'), 'w', encoding='utf-8') as f:
    f.write(master_front_svg)
with open(os.path.join(SITE_MUSCLE_DIR, 'master_mannequin_front.svg'), 'w', encoding='utf-8') as f:
    f.write(master_front_svg)

# Now build Master Composite Back SVG
back_base_paths = muscle_data.get('md_back_base', [])
master_back_svg = f'''<?xml version="1.0" encoding="utf-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="{VIEWBOX}" class="fitify-mannequin back-mannequin">
  <defs>
    <filter id="glow-back" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="2.5" result="blur" />
      <feComposite in="SourceGraphic" in2="blur" operator="over" />
    </filter>
  </defs>
  <!-- Base Body Mannequin Back -->
  <g id="back_base" fill="#1e2e2a" stroke="#2d453f" stroke-width="0.5">
'''
for p in back_base_paths:
    master_back_svg += f'    <path d="{p}" />\n'
master_back_svg += '  </g>\n  <!-- Back Muscle Groups -->\n'

back_groups = [
    ('traps', 'md_back_traps', 'Трапеции'),
    ('lats', 'md_back_lats', 'Широчайшие'),
    ('lower_back', 'md_back_lower_back', 'Поясница'),
    ('shoulders_back', 'md_back_shoulders_back', 'Задние дельты'),
    ('triceps', 'md_back_triceps', 'Трицепсы'),
    ('forearm_posterior', 'md_back_forearm_posterior', 'Предплечья'),
    ('glutes', 'md_back_glutes', 'Ягодицы'),
    ('hams', 'md_back_hams', 'Бицепс бедра'),
    ('calves', 'md_back_calves', 'Икры'),
    ('obliques_back', 'md_back_obliques', 'Косые мышцы'),
    ('abductors', 'md_back_abductors', 'Отводящие мышцы'),
    ('adductors_back', 'md_back_adductors', 'Приводящие мышцы'),
    ('neck_back', 'md_back_neck_back', 'Шея сзади')
]

for tag, file_key, label in back_groups:
    paths = muscle_data.get(file_key, [])
    master_back_svg += f'  <g id="back_{tag}" class="muscle-layer" data-name="{label}" fill="#00e699" opacity="0.15">\n'
    for p in paths:
        master_back_svg += f'    <path d="{p}" />\n'
    master_back_svg += '  </g>\n'

master_back_svg += '</svg>\n'

with open(os.path.join(OUT_DIR, 'master_mannequin_back.svg'), 'w', encoding='utf-8') as f:
    f.write(master_back_svg)
with open(os.path.join(SITE_MUSCLE_DIR, 'master_mannequin_back.svg'), 'w', encoding='utf-8') as f:
    f.write(master_back_svg)

print('Successfully created master_mannequin_front.svg and master_mannequin_back.svg!')
