import json

with open('site/fitify_exercise_map.json', 'r', encoding='utf-8') as f:
    map_data = json.load(f)

js_content = f"// Fitify 3D Video Mapping for Flexa exercises\nwindow.FITIFY_EX_MAP = {json.dumps(map_data, ensure_ascii=False)};\n"

with open('site/fitify_map.js', 'w', encoding='utf-8') as f:
    f.write(js_content)

print(f"Generated site/fitify_map.js with {len(map_data)} mapped exercises!")
