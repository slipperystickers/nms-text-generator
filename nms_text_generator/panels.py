"""Native panel face alignment; no meshes are stretched or edited.

Glyphs are authored using the Flat Panel footprint. Storage Panels expose their
plain BACK, with the rest buried. Dimensions were measured from Base Builder's
native assets, and are checked against those assets by the Blender tests.
"""
import math
from mathutils import Matrix

ITEMS = (
    ('BUILDFLATPANEL', 'Flat Panels', 'Original decorated Flat Panel face'),
    ('STORAGEPANEL', 'Storage Panels (back)', 'Plain square-cornered back face; same part count and layout'),
)
DEFAULT = 'BUILDFLATPANEL'
# Keep the historical recipe/calibration fallback above stable. Only fresh UI
# settings use Storage; saved and pre-selector signs must remain Flat Panels.
NEW_DEFAULT = 'STORAGEPANEL'
FLAT_FACE_Y = 0.2915039658546448
FLAT_FOOTPRINT = (3.0078125, 1.260742425918579)
STORAGE_FACE_CENTER = (-0.02734375, 0.0, 0.0283203125)
STORAGE_FACE_SIZE = (2.9921875, 1.250976800918579)
# Fit within the existing footprint in both axes using ONE uniform scale.
# Native aspect ratios differ slightly: the Storage face is about 0.26% narrower.
STORAGE_SCALE = min(a / b for a, b in zip(FLAT_FOOTPRINT, STORAGE_FACE_SIZE))

def validate(part_id):
    if part_id not in {item[0] for item in ITEMS}:
        raise ValueError('Unknown panel type: ' + str(part_id))
    return part_id

def from_flat_matrix(matrix, part_id=DEFAULT):
    validate(part_id)
    if part_id == DEFAULT:
        return matrix.copy()
    correction = (Matrix.Translation((0, FLAT_FACE_Y, 0))
                  @ Matrix.Scale(STORAGE_SCALE, 4)
                  @ Matrix.Rotation(math.pi, 4, 'X')
                  @ Matrix.Translation(tuple(-v for v in STORAGE_FACE_CENTER)))
    return matrix @ correction
