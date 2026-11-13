import json

with open('site/fitify/muscles/master_mannequin_front.svg', 'r', encoding='utf-8') as f:
    front_svg = f.read()

with open('site/fitify/muscles/master_mannequin_back.svg', 'r', encoding='utf-8') as f:
    back_svg = f.read()

js_content = f'''// Authentic Fitify Muscle Mannequin Vectors
window.FITIFY_FRONT_SVG = {json.dumps(front_svg)};
window.FITIFY_BACK_SVG = {json.dumps(back_svg)};
'''

with open('site/muscles.js', 'w', encoding='utf-8') as f:
    f.write(js_content)

print('Generated site/muscles.js successfully!')
