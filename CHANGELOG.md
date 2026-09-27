# Changelog

## 2.0.1 — SVG import cleanup hotfix

- Automatically remove redundant path sampling before stroke expansion and outline fitting.
- Combine stroke patches with consistent winding so overlaps cannot cancel into holes.
- Recover complex or numerically fragile outlines locally at 2048-pixel resolution instead of rejecting them at the vector-union limit. Trace closed contours, including openings, then fit panels along the outline as before.
- When an imported SVG needs outline simplification, offer **Simplify & Import** or **Cancel** before tracing it. Cancel preserves the previously loaded icon/settings. Simple SVGs load normally. Recovery can reduce details smaller than its sampling resolution; unsupported SVG effects and security/resource limits still apply.
- Reuse cleaned outlines and fitted previews across slider changes, import and generation to avoid repeated work.
- Fix the outline fitter's subdivision-depth variable being overwritten by panel dimensions.
- Preserve source files, saved SVG settings, existing generated objects, Text mode and both Base Builder dependencies. Existing icons change only on explicit Update.

## 2.0.0 — First official NMScribe launch

- Publish the NMScribe identity and approved branding, with five lettering styles and thirteen special characters.
- Launch contour-first SVG Icon / Sticker mode with accuracy/part-limit controls and editable native-part collections.
- Default both modes to Storage Panels (back), while preserving existing creations and Flat Panel support.
- Ship the complete offline instruction page and updated installation, editing, mounting and export guide.
- Keep Base Builder compatibility with or without Charon Forge; neither dependency is modified.

## 1.8.2 — Local launch candidate

- Storage Panels (back) is now the default for fresh Text and Icon / Sticker settings.
- Preserve saved panel choices and the Flat Panel fallback for old signs without panel metadata; no automatic conversion of existing geometry.
- Include a branded, self-contained offline instruction page, the full Markdown guide, and launch notes.
- Carry forward the contour-first SVG fitter, declaration import fix, five lettering styles, symbol support and approved NMScribe branding.

## 1.8.1 — Contour-first SVG fitting

- Accept ordinary Illustrator/W3C SVG DOCTYPE declarations without fetching external resources; keep custom entities/internal DTDs blocked.
- Replace the four-angle, area-first outline with vector-contour panels at arbitrary rotations, followed by overlapping interior fill.
- Remove hidden boundaries between overlapping SVG shapes and guard fill panels against crossing outlines or holes.
- Cover concave joins with safe inward overlaps and account for native inset faces during interior cleanup.
- Show outline/fill part counts and distinguish budget-driven simplification from an incomplete fill. Existing icons can be rebuilt with Update Selected Icon; text fonts are unchanged.
- Locally tested with the supplied Rebel Alliance and paw-print SVGs and real native Blender panels. Game validation remains separate.

## 1.8.0 — Experimental SVG icon/sticker mode

- Text / Icon mode switch immediately below the unchanged branding header.
- Offline SVG silhouette import with an accuracy slider, hard panel limit, fitted preview, and sampled coverage readout.
- Generates unmodified native Flat Panels or Storage Panels with uniform scales and coplanar front faces.
- Icons have separate collections and controls, saved SVG source, re-edit/update, undo and native JSON export. Text fonts are unchanged.
- Unsupported SVG features fail clearly; external resources and scripts are never loaded. This is approximate single-colour geometry, not a multicolour decal or exact curve converter.

## 1.7.9 — Measured header alignment

- Registered the Paint reference and Blender screenshot by their branding boxes to measure layout offsets.
- Corrected emblem size, title/credit position, and excess vertical spacing without regenerating the artwork.

## 1.7.8 — Paint-reference alignment

- Added top padding and nudged the slightly enlarged emblem up and right to follow the supplied Paint mockup.
- Preserved the approved artwork, typeset credit and premultiplied transparency.

## 1.7.7 — banner balance

- Reduced emblem size by 15 percent and the emblem/wordmark gap by one third.
- Centered the emblem vertically against the title and credit together; retained original artwork and transparency handling.

## 1.7.6 — banner spacing and credit

- Separated the emblem and wordmark with whitespace equal to half the emblem width.
- Enlarged the right-aligned typeset credit beneath the wordmark. No artwork regeneration or added decoration.

## 1.7.5 — original artwork and typeset credit

- Rebuilt the credit from the original approved artwork using conventional text rendering; original pixels outside the credit are unchanged.
- Added a Lanczos-filtered sidebar image instead of sampling the full-resolution logo directly at icon size.
- Use display-encoded RGB for the UI preview and preserve transparent alpha.
- Convert straight PNG alpha to premultiplied UI preview alpha, removing bright jagged fringes.

## 1.7.4 — continuous banner

- Removed the five-tile logo display that broke the artwork at icon boundaries.
- Display one continuous, top-aligned banner in a compact reserved row.
- Put the smaller author/year credit inside the graphic under the wordmark; removed the separate credit label.
- Retained deferred, failure-tolerant startup loading.

## 1.7.3 — startup fix

- Defer banner image datablock access until after add-on registration, fixing the missing tab on normal Blender startup.
- Banner failures now fall back to the text title without disabling the tool.
- Added restricted-registration and installed-startup regression checks.

## 1.7.2 — NMScribe local review

- Added the approved amber paneled NMScribe banner and right-aligned author/year credit. Sidebar tab stays NMS Text.
- Restored a normal single text field in the sidebar and re-edit dialog. No separate text-entry pop-out.
- Added case-insensitive `<br>`, `<br/>`, and `<br />` line breaks. Backslashes remain literal; other HTML is not supported.
- Older multiline signs display line breaks as `<br>` when loaded for editing without changing their rendered layout.

## 1.7.1 — local UI review

- App-first NMS Text header with a temporary Blender text icon, publication year,
  FuriousFurby (FF) credit and subtle CCB community donation credit.
- Removed the Furby badge and sidebar role-required notice; kept the CCB button.
- Added focused multiline text entry with Shift+Enter, literal backslashes,
  copy/paste, selection, navigation, undo/redo and cancel-safe drafts.
- Preserved old saved signs through versioned one-time escape conversion.
- Right-click editing stages text first, then the existing layout dialog; no
  generated panels change unless the final layout dialog is confirmed.

## 1.7.0 — local review build

- Added native-panel `- _ / \ ? ! | [ ] + = : .` to Boundary, Bulkhead, Orbit, Forge and
  Vector, with style-matched stroke widths and individual advances.
- Refined brackets, slashes and bars to 112% cap height, centered vertically;
  shortened hyphens by 20% without changing stroke thickness.
- Preserved every approved A-Z/0-9 placement and width, including Vector spacing.
- Added a literal-backslash escape (`\\`); existing `\n` multiline text still works.
- Added the FuriousFurby badge, creator credit, CCB community credit and an
  optional Discord invite button with the Traveller Toolkit role requirement.
- Added reproducible full 49-character reference scenes and silhouette sheets.
- No changes to Base Builder or Charon Forge; neither dependency is bundled.

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
