# -*- coding: utf-8 -*-
import json
import re
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding='utf-8')

session_dir = Path('auto_booking/training_data/session_2026-10-02_02-55-55')
recipe_file = session_dir / 'workflow_recipe.json'

with open(recipe_file, 'r', encoding='utf-8') as f:
    actions = json.load(f)

print(f'Total actions captured: {len(actions)}')

for a in actions:
    step = a['step']
    x, y = a['x'], a['y']
    t = a['time']

    xml_files = list(session_dir.glob(f'{step:03d}_*.xml'))
    clicked_elem = None
    screen_title = ""

    if xml_files and xml_files[0].stat().st_size > 0:
        try:
            tree = ET.parse(xml_files[0])
            for el in tree.iter():
                bounds = el.get('bounds', '')
                txt = (el.get('text') or el.get('content-desc') or '').strip()
                if not screen_title and txt and len(txt) > 3:
                    screen_title = txt[:35]

                m = re.findall(r'\[(\d+),(\d+)\]', bounds)
                if len(m) == 2:
                    x1, y1 = int(m[0][0]), int(m[0][1])
                    x2, y2 = int(m[1][0]), int(m[1][1])
                    if x1 <= x <= x2 and y1 <= y <= y2 and txt:
                        clicked_elem = txt
        except Exception:
            pass

    print(f"Step {step:02d} [{t}] Tap ({x:4d}, {y:4d}) | Element: '{clicked_elem or '-'}' | Screen: '{screen_title}'")
