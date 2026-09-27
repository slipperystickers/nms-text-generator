# Changelog

## 1.6.1 — compatibility update

- Added support for official Base Builder 7.0.0 and Charon Forge 0.1.0, using
  the new native-part hooks instead of requiring the removed `builder_v2` module.
- Charon Forge is optional: Base Builder 7.0.0 alone uses its standard native
  panel models/materials. The previous combined 18.0.8 add-on still uses its
  existing HD API without needing Forge.
- No changes to glyphs, spacing, part counts, native IDs or exported placements.
  Saved signs remain editable; installing does not regenerate existing objects.
- Resolve the active host builder at operation time, and preserve transactional
  replacement, selection safeguards, auto-switching and right-click editing.
- This add-on does not patch or modify either dependency.

## 1.6.0 — 2026-09-26

- First public release of Vector, the fifth A-Z/0-9 lettering style, including
  the refinements developed in the private 1.5.x builds below.

- Added a native Panel type choice: Flat Panels or the plain back of Storage
  Panels. Both use positive uniform scaling, unchanged game meshes and the same
  glyph layout/part count. No tilted-face construction is used.
- Panel choice is saved per sign, supported in right-click Edit NMS Text, and
  auto-switches one fully selected sign using the same safeguards as Font.
  Old signs default to Flat Panels; loading/installing never rebuilds them.
- Integrated the coplanar Vector overlap optimization: 626 parts for A-Z/0-9,
  at most 32 per character. TYNDUSTRIAL ASTRONAUTICS now uses 367 parts, including
  the corrected 23-part C with paired inward-facing terminals.
- Preserved the narrow I advance and Y optical spacing. Storage back faces are
  aligned to the Flat Panel surface and fitted within its reference footprint;
  the tiny native aspect-ratio difference is not corrected by stretching.
- Blender/export checks do not establish in-game loading performance. No claim
  that one part type loads faster than the other.
- Expanded the user guide for panel switching, updating existing signs, and
  hiding Blender's relationship lines without removing the text control.

## 1.5.2 — private development build

- Tightened Vector Y's adjacent letter gaps by 0.3 units per side at height 5.
  This is optical spacing: the full-width letter geometry is unchanged.
- Corrections scale with letter height and are capped at half the configured
  gap per side, preventing overlap at small or zero gaps. Word spaces and
  other fonts are unchanged. Regenerate existing text to update its spacing.
- Part-count optimization is still experimental and is not included.

## 1.5.1 — private development build

- Removed Vector I's full-cell side padding; it now advances by its actual
  0.64-unit width plus the configured letter gap.
- Other glyph geometry, widths and part counts are unchanged. Existing signs
  receive corrected spacing when regenerated or confirmed through Edit NMS Text.
- Added scaled/aligned spacing regression tests. Part-count optimization remains
  a separate research experiment and is not included in this package.

## 1.5.0 — private development build

- Added Vector as a fifth independent style, with a native-part thumbnail preview.
- Includes the approved matched-width/stroke alphabet, custom pointed terminals,
  softer D, corner-matched 4 and upright Orbitron-style 7.
- Existing font IDs and default remain unchanged; Vector supports the existing
  auto-switch, right-click editing, save/reopen and native export workflows.
- Added full-library, part-budget and native workflow regression coverage.

## 1.4.0 — initial public package

- Display names: Boundary, Bulkhead, Orbit and Forge, with stable saved-file IDs.
- Four complete A-Z/0-9 native Flat Panel lettering libraries and visual previews.
- Automatic font changes for a fully selected sign, ON by default.
- Right-click Edit NMS Text from a single panel, with apply/cancel behavior.
- Separate sign collections, controls, persistent settings and native JSON export.
- Full user guide, provenance notices, standalone tests and reproducible ZIP builder.
- Explicit Blender 5.1 minimum metadata; tested with Blender 5.1.2 on Windows.

## Private development history

- 1.3.1: fixed dialog invocation; initialized auto-switch to ON for older files.
- 1.3.0: added automatic switching and right-click editing.
- 1.2.0: added the three new lettering styles and preview picker.
- 1.1.0: replaced Cuboid Inner Walls with uniformly scaled Flat Panels.
- 1.0.0: initial separate NMS Text sidebar and native-part generator.
