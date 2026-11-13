import os, sys, zipfile, io, json, struct, re

DEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fitify_all_extracted')
XAPK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fitify.xapk')

dirs = {
    'videos': os.path.join(DEST_DIR, 'videos'),
    'audio': os.path.join(DEST_DIR, 'audio'),
    'images': os.path.join(DEST_DIR, 'images'),
    'svgs': os.path.join(DEST_DIR, 'converted_svgs'),
    'vector_xmls': os.path.join(DEST_DIR, 'vector_drawables_xml'),
    'animations': os.path.join(DEST_DIR, 'lottie_animations'),
    'databases': os.path.join(DEST_DIR, 'databases_and_json'),
    'fonts': os.path.join(DEST_DIR, 'fonts'),
    'shaders': os.path.join(DEST_DIR, 'shaders_3d'),
    'translations': os.path.join(DEST_DIR, 'translations'),
    'raw_base_apk': os.path.join(DEST_DIR, 'raw_base_apk'),
}

for d in dirs.values():
    os.makedirs(d, exist_ok=True)

stats = {k: 0 for k in dirs.keys()}
stats['images_bytes'] = 0
stats['videos_bytes'] = 0
stats['audio_bytes'] = 0

def convert_axml_to_svg(data):
    try:
        if len(data) < 40 or data[:2] != b'\x03\x00':
            return None
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
        
        if 'vector' not in strings and 'pathData' not in strings:
            return None
        
        paths = [s for s in strings if (s.startswith('M') or s.startswith('m')) and len(s) > 10]
        if not paths:
            return None
        
        path_elements = []
        for p in paths:
            # Clean up length prefixes if present
            clean_p = re.sub(r'^[\x00-\x1f]+', '', p).strip()
            if clean_p.startswith('M') or clean_p.startswith('m'):
                path_elements.append(f'  <path d="{clean_p}" fill="currentColor" />')
        
        if not path_elements:
            return None
            
        svg = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" style="color: #00e699;">\n'
            + '\n'.join(path_elements) + '\n'
            '</svg>\n'
        )
        return svg
    except Exception:
        return None

print(f'Starting extraction from {XAPK_PATH}...')

with zipfile.ZipFile(XAPK_PATH, 'r') as xz:
    # 1. First unpack Base APK completely
    base_bytes = xz.read('com.fitifyworkouts.bodyweight.workoutapp-10440.apk')
    with zipfile.ZipFile(io.BytesIO(base_bytes)) as bz:
        print('Unpacking base APK entries...')
        for name in bz.namelist():
            data = bz.read(name)
            # Full raw extraction
            target_raw = os.path.join(dirs['raw_base_apk'], name.replace('/', os.sep))
            os.makedirs(os.path.dirname(target_raw), exist_ok=True)
            with open(target_raw, 'wb') as f:
                f.write(data)
            stats['raw_base_apk'] += 1
            
            basename = os.path.basename(name)
            lower = name.lower()
            
            # Categorize
            if lower.endswith('.mp4'):
                with open(os.path.join(dirs['videos'], basename), 'wb') as f:
                    f.write(data)
                stats['videos'] += 1
                stats['videos_bytes'] += len(data)
            elif any(lower.endswith(ext) for ext in ['.m4a', '.mp3', '.wav', '.ogg']):
                with open(os.path.join(dirs['audio'], basename), 'wb') as f:
                    f.write(data)
                stats['audio'] += 1
                stats['audio_bytes'] += len(data)
            elif any(lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp']):
                with open(os.path.join(dirs['images'], basename), 'wb') as f:
                    f.write(data)
                stats['images'] += 1
                stats['images_bytes'] += len(data)
            elif lower.endswith('.ttf') or lower.endswith('.otf'):
                with open(os.path.join(dirs['fonts'], basename), 'wb') as f:
                    f.write(data)
                stats['fonts'] += 1
            elif any(lower.endswith(ext) for ext in ['.glsl', '.vert', '.frag']):
                with open(os.path.join(dirs['shaders'], basename), 'wb') as f:
                    f.write(data)
                stats['shaders'] += 1
            elif lower.endswith('.json'):
                if 'anim' in lower or 'loading' in lower or 'lottie' in lower:
                    with open(os.path.join(dirs['animations'], basename), 'wb') as f:
                        f.write(data)
                    stats['animations'] += 1
                else:
                    # Rename to avoid collisions if nested
                    safe_name = name.replace('/', '__')
                    with open(os.path.join(dirs['databases'], safe_name), 'wb') as f:
                        f.write(data)
                    stats['databases'] += 1
            elif 'res/drawable' in lower and lower.endswith('.xml'):
                with open(os.path.join(dirs['vector_xmls'], basename), 'wb') as f:
                    f.write(data)
                stats['vector_xmls'] += 1
                # Try convert to SVG
                svg = convert_axml_to_svg(data)
                if svg:
                    svg_name = os.path.splitext(basename)[0] + '.svg'
                    with open(os.path.join(dirs['svgs'], svg_name), 'w', encoding='utf-8') as f:
                        f.write(svg)
                    stats['svgs'] += 1

    # 2. Extract high-res drawables from split config APKs
    split_apks = ['config.xxxhdpi-10440.apk', 'config.xxhdpi-10440.apk', 'config.xhdpi-10440.apk', 'config.hdpi-10440.apk']
    for s_apk in split_apks:
        if s_apk in xz.namelist():
            s_bytes = xz.read(s_apk)
            with zipfile.ZipFile(io.BytesIO(s_bytes)) as sz:
                for name in sz.namelist():
                    lower = name.lower()
                    if any(lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp']):
                        basename = os.path.basename(name)
                        out_path = os.path.join(dirs['images'], basename)
                        # Overwrite if larger resolution
                        data = sz.read(name)
                        if not os.path.exists(out_path) or len(data) > os.path.getsize(out_path):
                            with open(out_path, 'wb') as f:
                                f.write(data)
                            stats['images'] += 1
                            stats['images_bytes'] += len(data)

    # 3. Extract Russian strings
    if 'config.ru-10440.apk' in xz.namelist():
        ru_bytes = xz.read('config.ru-10440.apk')
        with zipfile.ZipFile(io.BytesIO(ru_bytes)) as rz:
            for name in rz.namelist():
                if name.endswith('.arsc'):
                    with open(os.path.join(dirs['translations'], 'resources_ru.arsc'), 'wb') as f:
                        f.write(rz.read(name))
                    stats['translations'] += 1

# Generate an index README.md in the extraction folder
readme = f"""# Полный архив выгруженных файлов Fitify Workouts

Все файлы успешно извлечены из оригинального `com.fitifyworkouts.bodyweight.workoutapp_10440.xapk`.

## Структура папок:

1. **`videos/`** ({stats['videos']} файлов, {stats['videos_bytes'] / (1024*1024):.2f} MB):
   - Все видео-петли упражнений (MP4, 60fps / 30fps), адаптированные для тренировочного таймера.

2. **`audio/`** ({stats['audio']} файлов, {stats['audio_bytes'] / (1024*1024):.2f} MB):
   - Голосовые подсказки тренера ElevenLabs (женский студийный голос) для каждого упражнения + системные фразы (Next exercise, Warmup complete и др.).

3. **`images/`** ({stats['images']} файлов, {stats['images_bytes'] / (1024*1024):.2f} MB):
   - Стоп-кадры, постеры упражнений, графика анатомии и тела в максимальном разрешении (WebP, PNG, JPG).

4. **`converted_svgs/`** ({stats['svgs']} файлов):
   - Векторные SVG-иконки, сконвертированные напрямую из Android VectorDrawable XML!

5. **`vector_drawables_xml/`** ({stats['vector_xmls']} файлов):
   - Оригинальные Android Vector XML файлы приложения.

6. **`lottie_animations/`** ({stats['animations']} файлов):
   - Векторные Lottie JSON-анимации загрузки и плеера.

7. **`databases_and_json/`** ({stats['databases']} файлов):
   - Полная база упражнений `exercises_bodyweight.json`, база Room coaching, связи сходства упражнений.

8. **`fonts/`** ({stats['fonts']} файлов):
   - Шрифты интерфейса (Anta.ttf и др.).

9. **`shaders_3d/`** ({stats['shaders']} файлов):
   - 3D шейдеры движка Korender (GLSL, vert, frag) для рендеринга освещения и персонажей.

10. **`raw_base_apk/`** ({stats['raw_base_apk']} файлов):
   - Полная пофайловая распаковка базового APK-пакета (все 100% файлов без фильтрации).
"""

with open(os.path.join(DEST_DIR, 'README.md'), 'w', encoding='utf-8') as f:
    f.write(readme)

print('\n=========================================')
print('EXTRACTION FINISHED SUCCESSFULLY!')
for k, v in stats.items():
    print(f'  {k}: {v}')
print(f'Destination folder: {DEST_DIR}')
print('=========================================')
