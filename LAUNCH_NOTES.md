# NMScribe v2.0 — First Official Launch

**No Man's Scribe** brings our lettering tool and new icon/sticker workflow together
under the NMScribe name. This is the first official launch; the earlier v1.x
releases were development and preview releases. Blender reports version **2.0.0**.

Native-panel lettering and SVG icons for No Man's Sky Base Builder.
By FuriousFurby(FF) — 2026. Donated to the Community by Corvette Class Builders (CCB).

## What's included

- Five lettering styles: Boundary, Bulkhead, Orbit, Forge and Vector.
- A-Z, 0-9 and thirteen symbols: `- _ / \ ? ! | [ ] + = : .`.
- Simple text entry with `<br>` line breaks, size, spacing, alignment and orientation controls.
- Font previews, automatic font/panel switching for a fully selected sign, and right-click text editing from one panel.
- **Icon / Sticker mode:** import a local SVG, follow its contour with native panels, then fill the interior. Accuracy and a hard part cap let you balance detail and piece count.
- **Storage Panels (back) by default in both modes.** Flat Panels remains available. Existing saved choices are preserved.
- Separate editable collections, parent controls, saved settings and native-part JSON export.
- A complete offline instruction page included in the ZIP and supplied separately.

## Install or update

Install **NMS_Text_Generator_2.0.0.zip** through Blender's **Edit > Preferences > Add-ons > Install from Disk**, then enable **NMScribe for Blender Base Builder**. Do not extract the installer or use GitHub's Source code ZIP. Save your work and restart Blender after updating. In the 3D Viewport, press **N** and open **NMS Text**.

No Man's Sky Base Builder must be installed separately. Charon Forge is optional.
NMScribe does not modify either dependency or bundle game models/textures.

Read **NMScribe_Instructions.html** for the complete walkthrough. It works offline
and includes troubleshooting, native export, and both editing workflows.

## Existing creations

Opening old files does not rebuild them. Saved Flat Panel choices stay Flat;
select Storage explicitly to convert them. To apply the improved SVG fitting,
select an icon panel, choose **Load Selected Icon Settings**, then **Update Selected Icon**.
Back up hand-edited work: rebuilding replaces manual changes to generated panels.

## Important limits

SVG mode is experimental, single-colour panel geometry—not an exact curve trace,
texture decal, bitmap converter or arbitrary font importer. Part limits take
precedence over accuracy. Prepare SVGs as plain paths; expand text, masks and
other unsupported effects. Native faces remain flat and uniformly scaled.

Keep the `.blend` as the editable master: exported JSON does not retain generator
settings. Use your existing Base Builder workflow to bring exported native parts
into NMS; NMScribe never writes live saves itself.

Blender 5.1.2 / Windows is the tested platform. Legacy combined Base Builder
remains supported; current generation/export is tested with the split Base Builder
both with and without Charon Forge. In-game, console and multiplayer behavior are
not certified by the offline Blender checks.

Community: [CCB / Traveller Toolkit](https://discord.gg/arbW3DvM5y).
Thanks to DjMonkey for Base Builder and Kuma for Charon Forge.

Code: GPL-3.0-or-later. See the included LICENSE and NOTICE.md for attribution and provenance.
