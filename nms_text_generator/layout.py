"""Deterministic glyph placement; deliberately independent of Blender."""
import json
import math
import string
from functools import lru_cache
from pathlib import Path

MAX_PARTS = 3000
MAX_INPUT = 2000
# Stable identifiers intentionally retain their development names so existing
# saved signs and enum values remain compatible. Only display names change.
FONTS = (('FUTURE_Z','Boundary','glyphs.json'),
         ('INDUSTRIAL','Bulkhead','fonts/industrial.json'),
         ('ORBITAL','Orbit','fonts/orbital.json'),
         ('FOUNDRY','Forge','fonts/foundry.json'),
         ('VECTOR','Vector','fonts/vector.json'))

# Optical side-bearing correction, in reference-height units. Y's full-width
# tips need less spacing than its largely empty lower half suggests. Keep the
# geometry intact and never consume more than half the gap on either side.
OPTICAL_BEARINGS = {'VECTOR': {'Y': .3}}

@lru_cache(maxsize=None)
def library(font='FUTURE_Z'):
    paths={key:path for key,name,path in FONTS}
    if font not in paths:
        raise ValueError('Unknown font: '+str(font))
    data = json.loads((Path(__file__).parent/paths[font]).read_text(encoding='utf-8'))
    data.setdefault('max_parts_per_character',max(map(len,data['glyphs'].values())))
    expected = set(string.ascii_uppercase + string.digits)
    if set(data['glyphs']) != expected:
        raise ValueError('The packaged glyph library is incomplete.')
    for char, records in data['glyphs'].items():
        if not 1 <= len(records) <= data['max_parts_per_character']:
            raise ValueError(f'Invalid part count for {char}.')
        if not math.isfinite(data['widths'][char]) or data['widths'][char] <= 0:
            raise ValueError(f'Invalid width for {char}.')
        for r in records:
            if r['ObjectID'] != '^BUILDFLATPANEL':
                raise ValueError('Unapproved part in glyph library.')
            for key in ('Position', 'Up', 'At'):
                if len(r[key]) != 3 or not all(math.isfinite(v) for v in r[key]):
                    raise ValueError(f'Invalid {key} for {char}.')
    return data

def normalize(text):
    if len(text) > MAX_INPUT:
        raise ValueError(f'Text input is limited to {MAX_INPUT} characters.')
    text = text.replace('\\n', '\n').replace('\r\n', '\n').replace('\r', '\n')
    text = ''.join(c.upper() if c in string.ascii_lowercase else c for c in text)
    bad = sorted(set(text) - set(string.ascii_uppercase + string.digits + ' \n'))
    if bad:
        raise ValueError('Unsupported characters: ' + ', '.join(repr(c) for c in bad) + '. Use A-Z, 0-9, spaces and line breaks.')
    return text

def plan(text, height=5.0, letter_gap=1.0, word_gap=3.0, line_gap=1.5, alignment='LEFT', font='FUTURE_Z'):
    for name, value in [('height',height),('letter gap',letter_gap),('word gap',word_gap),('line gap',line_gap)]:
        if not math.isfinite(value) or value < 0 or (name == 'height' and value <= 0):
            raise ValueError(f'Invalid {name}.')
    if alignment not in ('LEFT','CENTER','RIGHT'):
        raise ValueError('Invalid alignment.')
    text = normalize(text)
    data = library(font)
    scale = height / data['height']
    placements, widths = [], []
    part_count = 0
    for line_index, line in enumerate(text.split('\n')):
        x = 0.0
        row = []
        previous_glyph = None
        for c in line:
            if c == ' ':
                x += word_gap
                previous_glyph = None
                continue
            if previous_glyph:
                bearings = OPTICAL_BEARINGS.get(font, {})
                correction = sum(min(letter_gap/2, bearings.get(g, 0)*scale)
                                 for g in (previous_glyph, c))
                x += letter_gap - correction
            row.append({'char':c, 'x':x, 'y':-line_index*(height+line_gap), 'line':line_index})
            x += data['widths'][c]*scale
            previous_glyph = c
            part_count += len(data['glyphs'][c])
        widths.append(x)
        shift = 0 if alignment == 'LEFT' else -x/2 if alignment == 'CENTER' else -x
        for p in row:
            p['x'] += shift
        placements.extend(row)
    if not placements:
        raise ValueError('Enter at least one letter or number.')
    if part_count > MAX_PARTS:
        raise ValueError(f'{part_count:,} parts exceeds the {MAX_PARTS:,}-part safety limit. Generate smaller sections.')
    return {'text':text, 'placements':placements, 'scale':scale, 'part_count':part_count,
            'character_count':len(placements), 'line_widths':widths, 'lines':len(widths)}
