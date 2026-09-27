# NMScribe — complete user guide

NMScribe (No Man's Scribe), by FuriousFurby(FF) — 2026. Official launch v2.0; SVG import hotfix 2.0.1.
Donated to the Community by Corvette Class Builders (CCB).

Create editable panel lettering and SVG silhouettes from real No Man's Sky parts,
not Blender text meshes or image decals. Each creation has its own collection,
parent control and saved settings. **Storage Panels (back)** is the default for
new Text and Icon / Sticker settings; Flat Panels is still available. Only the
front silhouette is intended to show; bury the rear geometry in a mounting surface.

This guide is also supplied as **NMScribe_Instructions.html**. Open it in any
browser to read offline, use Ctrl-F to search, or Ctrl-P to print/save as PDF.

## Contents

- [Install and find the panel](#install-and-find-the-panel)
- [Your first sign](#your-first-sign)
- [SVG icons and stickers](#svg-icons-and-stickers)
- [Styles and previews](#styles-and-previews)
- [Text and layout settings](#text-and-layout-settings)
- [Orientation and mounting](#orientation-and-mounting)
- [Automatic font and panel switching](#automatic-font-and-panel-switching)
- [Edit a completed sign](#edit-a-completed-sign)
- [Move and organize signs](#move-and-organize-signs)
- [Colours and materials](#colours-and-materials)
- [Save and export](#save-and-export)
- [Limits and worked examples](#limits-and-worked-examples)
- [Troubleshooting](#troubleshooting)
- [Update or uninstall](#update-or-uninstall)

## SVG icons and stickers

The **Text / Icon / Sticker** switch sits immediately beneath the logo/community header. Text mode and all approved fonts are unchanged. Icon mode is an experimental geometry fitter, not a texture/decal importer.

1. Choose **Icon / Sticker**, then **Import SVG**. Select a local `.svg` file (maximum 1 MB).
2. Adjust **Accuracy** and **Part limit**. After a short pause, the preview updates without changing any objects in your scene. Amber shows the fitted panel area; red shows target detail not covered at the sampling resolution.
3. Read the actual planned panel count before generating. The hard part limit is never exceeded. If the limit is reached, some detail remains omitted; either raise the limit or accept a simpler result. Tiny features and small islands can disappear at lower accuracy or tight budgets.
4. Keep the default **Storage Panels (back)** or choose Flat Panels, then set icon height, orientation, face offset, and palette. Height scales the whole design uniformly and does not itself change part count. The preview is based on the Flat Panel footprint; Storage Panel faces have a very slightly different aspect ratio.
5. Position the 3D Cursor at the desired **centre** of the icon and choose **Generate New Icon**. This creates a separate collection with a parent control and native NMS parts. Bury rear geometry in a mounting surface, as with text.
6. To revise it later, select any generated panel and right-click **Edit NMS Icon / Sticker**, or use **Load Selected Icon Settings** in the sidebar. Adjust the preview, then click **Update Selected Icon**. The original control's position, rotation, uniform scale and untagged attachments remain. Generated panels and their manual edits are replaced; Ctrl-Z undoes the update. Default palette keeps the original group's colour/material, not individual panel recolouring.
7. Save your `.blend`. The SVG source is stored with the icon, so re-editing does not depend on the original file remaining on disk. **Export Icon JSON** exports native game parts only, not the SVG, preview or parent control.

### SVG support and limitations

- **One-click simplification:** simple SVGs load normally. For a complex outline, NMScribe asks **Simplify SVG?** Choose **Simplify & Import** to retrace the outline with fewer line segments, or **Cancel** to keep the current icon/settings. No separate editor, external converter or upload is needed. The original SVG file is never changed. Internally, difficult stroke/outline unions use a 2048-pixel silhouette trace before contour simplification and native panel fitting; the sidebar reports when this is used.
- Cleanup and the panel budget are separate. Recovery may reduce sub-pixel details; the Accuracy slider and part cap can cause additional approximation afterward. Raise the part limit when the preview reports omitted detail. Neither 100% Accuracy nor successful import guarantees an exact reproduction.

- Paths with lines, cubic/quadratic curves and elliptical arcs; rectangles (including rounded rectangles), circles, ellipses, polygons, polylines and lines.
- Group transforms, internal `use` references, inline styles/presentation attributes, even-odd/nonzero holes, and simple solid strokes with common caps/joins.
- All visible colours merge into **one silhouette**. White-filled shapes are solid, not erasers: use real holes/compound paths for cutouts. Opacity is treated as visible/not-visible, not translucent panel geometry. Gradients are treated as solid fills.
- The imported artwork is tightly fitted to its geometry bounds, not the SVG page's whitespace. Root page dimensions/viewBox are not used as a clipping mask; keep geometry within the intended artwork area before export.
- Convert text to outlines. Expand clipping paths, masks, filters, dashed strokes and non-scaling strokes before importing. Export styles inline, not as a stylesheet. Embedded/raster images, scripts, external resources, nested SVG viewports and viewBox-based symbol instances are unsupported. No external content is fetched or executed.
- The fitter now traces the visible vector outline first, rotating native panels to follow each contour edge, then overlaps panels to fill the interior. Hidden edges inside overlapping SVG shapes are removed. Both outline and fill rectangles are checked against the vector boundary, including holes; the meshes themselves are never clipped, stretched or tilted.
- Accuracy controls contour simplification and cleanup sampling. It is **not** a guarantee of perfectly smooth curves or a strictly increasing part count at each slider step. Curves are approximated with straight segments; very sharp tips and native beveled rims can retain tiny differences. Interior cleanup allows extra overlap for the Flat Panel's inset face.
- **Part limit takes precedence over Accuracy.** If the outline would consume most of the budget, it is simplified to leave room for interior panels. The sidebar reports this and separates outline/fill counts. If small gaps remain at the cap, increase the limit or reduce accuracy. A setting of 100% does not override the limit or mean an exact SVG reproduction.
- Standard external SVG DOCTYPE declarations (including Illustrator's SVG 1.1 declaration) are accepted and ignored locally. No DTD URL is fetched. Custom entities and internal DTD subsets remain blocked.
- **Sampled coverage** measures raster samples, not an exact area proof for the native meshes. Even 100% at that resolution can retain subpixel gaps or contour differences. Inspect the actual panel build and verify it in game before relying on it for final artwork.
- This version is tested offline in Blender, not certified in-game or in multiplayer. It supports one icon per update; it never updates all selected signs or icons automatically.

## Install and find the panel

### Requirements

Tested with **Blender 5.1.2 for Windows** using either:

- The previous combined **18.0.8 Base Builder development build**. No Charon Forge needed.
- The new official **Base Builder 7.0.0 alone**, using its standard native models/materials.
- **Base Builder 7.0.0 + Charon Forge 0.1.0**, using Charon Forge's HD models/textures.

**Charon Forge is optional, not a requirement to generate or export text.** The
version numbers above belong to different release lines. Native IDs, transforms,
lettering designs and part counts are identical across these configurations; the
Blender model/material display can differ. Standard models do not have Forge's HD
textures. Required assets are `BUILDFLATPANEL` and, for Storage mode, `STORAGEPANEL`.
Other operating systems and dependency builds are not yet verified.

Base Builder must be installed separately. The text generator does not contain
game meshes, textures, font files, or Base Builder's own code. You do not need
system fonts, an online account, or additional Python packages to use the generator.

### Installation steps

1. Install and enable the compatible **No Man's Sky Base Builder** first. With the new
   split release, optionally enable **Charon Forge** too for HD models/textures.
2. Download the installable **NMS_Text_Generator_<version>.zip** from the project's
   Releases page. GitHub's automatic Source code ZIP is not the installer.
3. Open **Edit > Preferences > Add-ons** in Blender.
4. Open the menu at the top-right of the add-on list and choose **Install from Disk**.
5. Select the installer ZIP. Do not extract it first.
6. Enable **NMScribe for Blender Base Builder** if necessary (older releases used the name NMS Text Generator).
7. After updating an already loaded installation, save your work and restart Blender.
8. Hover over the **3D Viewport**, press **N**, and choose the **NMS Text** tab.

This is a separate tab, not a section inside the Base Builder tab. Widen the
sidebar or scroll its vertical tabs if it is difficult to find.

## Your first sign

1. Switch to **Object Mode** using the viewport's mode dropdown.
2. Position the **3D Cursor** at the sign's baseline anchor. For a simple test,
   choose **Shift-S > Cursor to World Origin**.
3. Enter `WELCOME` in Text and choose a style from Font.
4. Keep **Storage Panels (back)**, height 5, the default gaps, and **Flat (XY)**. Flat (XY) is an orientation, not the panel type.
5. Leave Colour / material at **Default / keep on replace**.
6. Check the part count and click **Generate New Text**.
7. The panels are selected. Use **View > Frame Selected** or **Numpad .** to find them.
8. Switch to **Material Preview** or **Rendered** shading to inspect native materials.
9. Save the `.blend` file to preserve editable text settings.

**Generate New Text always adds another sign.** To change one you have already
made, use the font-switching or editing workflows below.

## Styles and previews

| Release name | Former development name | Character |
| --- | --- | --- |
| Boundary | Future Z | Wide technical lettering, developed with an external visual reference |
| Bulkhead | Industrial Block | Squared utility lettering |
| Orbit | Orbital Octagon | Wide geometric lettering with chamfered corners |
| Forge | Foundry Slab | Rectangular slab serifs and contrasting stroke widths |
| Vector | Orbitron-inspired ship study | Matched-width technical lettering with custom flat-capped diagonals and a softer D |

Use the **Font dropdown**, or click the preview tile beneath it to open the
thumbnail picker. Both controls change the same setting. The thumbnails show
fixed `ABC / 123` samples rendered from native parts, not your current text.

Each style includes A-Z, 0-9 and `- _ / \ ? ! | [ ] + = : .`. These are predefined placements, not arbitrary
TTF/OTF conversion. No system font installation is needed. Some glyphs intentionally
share shapes, including O and zero. See NOTICE.md for credits and reference provenance.

**Vector:** select Vector from the same Font dropdown or thumbnail picker. It
supports automatic switching and right-click editing just like the other styles.
The letter bodies use a common width and stroke thickness; I uses its actual narrow
width plus the normal letter gap (no extra side padding). The 1 remains centered
in its wider cell, while Q has an external tail. Its zero is slashed and
its 7 has an upright right stem. C has paired inward-facing return terminals.
The coplanar overlap optimization uses 4–32 panels per character, 626 for one
A-Z/0-9 set. `TYNDUSTRIAL ASTRONAUTICS` uses 367 panels. Watch the displayed
part count; the 3,000-part guard still applies (93 X characters use 2,976 panels;
94 exceed the guard).
No system font file or additional package is required. After updating, save your
work and restart Blender before looking for Vector.

### Panel type: Flat or Storage

- **Storage Panels (back)** is the default for fresh settings in both modes. It uses the plain flat back, with the detailed front
  buried in the mounting surface. There is no tilted-face construction.
- **Flat Panels** is still available and uses the original decorated native front face.
- This changes the item, not the glyph design, spacing or number of pieces.
  Storage faces are uniformly scaled to fit within the Flat Panel footprint.
  Their aspect ratios differ slightly (about 0.26%); neither asset is stretched.
- Choose the type before Generate New Text. With Auto-switch ON and all parts
  of exactly one sign selected, changing Panel type rebuilds it immediately.
  As with font changes, this replaces manual edits to its generated panels.
- From one selected panel, right-click **Edit NMS Text** to change the saved
  panel type in the dialog. **OK** applies; **Cancel** leaves the sign unchanged.
- Saved signs, icons and explicitly saved sidebar choices keep their selected
  panel type. Very old signs with no panel-type metadata still fall back to Flat
  Panels. Installing an update or opening a file does not regenerate geometry.
- JSON export contains the actual `^BUILDFLATPANEL` or `^STORAGEPANEL` IDs.
  Compare loading in your own NMS build; Blender tests do not establish which
  part type loads faster, more reliably, or identically for other players.

## Text and layout settings

### Text entry

Supported input is **A-Z, 0-9, spaces, line breaks**, and these thirteen symbols:
`- _ / \ ? ! | [ ] + = : .`. Lowercase a-z converts to uppercase. Commas, accented
characters and other unlisted symbols are rejected with an explanation rather
than silently omitted. Symbols work with every font and both panel types.

Type directly in the normal sidebar **Text** field. Use `<br>` for a new line:
`WELCOME<br>TRAVELLERS`. `<br/>`, `<br />` and uppercase `<BR>` also work.
Repeated tags create blank lines. There is no separate text-entry window.
This is a line-break shorthand, not an HTML renderer: formatting tags, scripts,
and entities are not supported. Use the existing alignment and spacing controls.

Type backslash as `\`, exactly once. There are no escape shortcuts for new text:
`\n` means a backslash followed by N. Pasted line breaks work normally. Repeated
spaces add additional space. Older saved signs convert their former escape
notation once when loaded for editing or regeneration, preserving their layout.

Hyphens sit at mid-height and underscores at the baseline. Brackets, slashes and
vertical bars are 12% taller than letters, extending 6% above the cap height and
6% below the baseline. Question/exclamation marks retain normal character height.
Symbols have individual widths, rather than full-letter padding.
The period is a baseline-aligned square dot matching the font's stroke weight,
made from three overlapping native panels. It also works in numbers such as `3.14`.

### Creator and community

The sidebar displays the amber paneled **NMScribe** banner, with **by:
FuriousFurby(FF) - 2026** aligned right underneath and a subtle **Donated to the Community by
Corvette Class Builders (CCB)** credit. Click **CCB / Traveller Toolkit** to open
the server invite in your browser.
After joining, obtain the appropriate server role to see **Traveller Toolkit**.
The link does not grant the role or join automatically. The tool itself remains
offline; using Discord is optional. Branding follows your Blender theme.

### Settings reference

| Setting | Meaning |
| --- | --- |
| Letter height | Uniform size of the selected glyph design. Default: 5 Blender distance units. |
| Letter gap | Space between adjacent characters, excluding typed spaces. Default: 1. |
| Space width | Advance added for each typed space. Default: 3. |
| Line gap | Extra distance in addition to Letter height between baselines. Default: 1.5. |
| Left | Starts each line's layout at the cursor/control origin. |
| Center | Centers each line's layout width around the origin. |
| Right | Ends each line's layout at the origin. |
| Face offset | Additional movement along the sign's local front-facing direction. |

Changing Letter height does **not** scale the gaps automatically. If you double
the height and want similar proportions, double the gaps too. A typed space uses
Space width, not Space width plus a Letter gap on each side.

Alignment uses defined glyph widths, not pixel-tight visible outlines. Tails such
as Q can extend beyond the main character height/width. Parent scaling also affects
final size. Blender units are not a guarantee of final game dimensions.

## Orientation and mounting

The 3D Cursor anchors **new** text. Choose:

| Orientation | Placement |
| --- | --- |
| Flat (XY) | Letters lie in XY, facing +Z before later rotations. |
| Upright (XZ) | Letters stand in XZ, facing -Y before later rotations. |
| 3D Cursor rotation | Uses the cursor's complete position and rotation. |

Positive Face offset moves outward along the sign's local front direction;
negative values move inward. The glyph recipes already have small front-surface
offsets, so this field is an adjustment rather than an exact burial-depth value.

1. Place the cursor near your mounting surface and choose an orientation.
2. Generate the sign and click **Select Control**.
3. Move/rotate the control until the sign faces the desired direction.
4. Sink the rear panels into the backing while leaving the letter faces visible.
5. Inspect from the front and adjust depth as needed.

The generator does not create a backing, snap to walls, conform to curved
surfaces, remove native texture seams, or bend text around a curved baseline.

Moving the cursor later does not move existing signs. Re-editing preserves the
existing control transform. Use the control to rotate existing text; Orientation
in the sidebar is used when generating new text.

## Automatic font and panel switching

**Auto-switch selected text defaults ON.** Older files are initialized to ON
once when the migration first runs; your later ON/OFF choice is saved with the file.

1. Select all panels of **one** generated sign. They are already selected just
   after generation. To select them again, click one panel, then **Select Parts**.
2. Keep unrelated objects unselected.
3. Change Font in the dropdown or thumbnail picker, or change Panel type.
4. The sign rebuilds automatically—no Replace button or confirmation required.

This operation changes only the chosen font or panel type, using that sign's
**saved text, size and spacing**. It does not apply unrelated draft values typed
into the sidebar. The control keeps
its position and rotation, and the new panels remain selected.

Auto-switch does not run on one panel, partial selections, the control alone,
multiple signs, or mixed selections. A queued change is abandoned if selection
changes before it can run. Use right-click editing from a single selected panel.

To choose a style for a new sign without changing an existing selected sign,
deselect it or turn Auto-switch OFF first. Only Font and Panel type auto-rebuild;
other fields require an explicit edit/apply action.

## Edit a completed sign

### Recommended: right-click Edit NMS Text

1. In Object Mode, select **any one panel** of the sign.
2. Right-click in the 3D Viewport and choose **Edit NMS Text**.
3. Edit the text directly in the dialog's **Text** field; use `<br>` for new lines.
4. The layout dialog loads the sign's style, size and spacing. Adjust these and
   check the displayed part count.
5. **OK** rebuilds the sign. **Cancel** leaves it unchanged.

The same Edit button is in the NMS Text sidebar. All panels may also be selected.
When multiple signs are selected, the active object's sign is the edit target;
select one panel of the intended sign to avoid ambiguity.

The dialog does not modify scene geometry as you change fields, including Font.
This keeps Cancel safe. Confirm with OK to apply. The sidebar then synchronizes
to the edited sign. Editing works after reopening the original `.blend` file.

### Alternative: sidebar settings

1. Select one panel and click **Load Selected Text Settings**.
2. Change the required fields in the sidebar.
3. Click **Replace Selected Text**, then confirm.

Load Selected Text Settings only loads values; it does not rebuild. The confirmation
belongs to this explicit replacement workflow, not to automatic font switching.

### What is preserved?

Rebuilding preserves the parent control and its transform, other signs, and
untagged user-added child objects. The collection/control name updates with the text.

**Manual edits to generated panels are replaced**, including per-panel movement
and recolouring. Use Ctrl-Z to undo and save a backup `.blend` before manual detailing.

## Move and organize signs

Select one panel and click **Select Control**. The sign's parent Empty is selected.
Use **G** to move, **R** to rotate, or **S** to scale the whole sign uniformly.

Avoid axis-only scale, negative/mirrored scale or shear. Export rejects invalid
transforms. For a precise size, edit Letter height instead of stretching panels.

Moving all panels directly can look correct, but a later rebuild places them
relative to the unchanged parent. Move the **control** if the new location should
survive re-editing.

Keep the collection, parent relationship and custom metadata intact. Do not join
the panels into one mesh or remove their parent if you want native export and editing.
Avoid moving the control into additional collections; replacement checks ownership.

Generate again for another independently editable sign. Ordinary duplication of
managed hierarchies is not a verified replacement for Generate New Text. To mix
styles within a phrase, use separate generated signs.

### Hide the connection lines

The dotted lines connecting panels to the control are Blender's **Relationship
Lines**, not exported game objects. Open the **Viewport Overlays** dropdown
(beside the overlapping-circles icon at the top-right of the 3D Viewport), then
under **Objects**, uncheck **Relationship Lines**.

This only changes that viewport's display. It keeps the parent control, text
editing and native export intact, and leaves other overlays available. Do not
unparent the panels or delete the control to remove the lines. Save the `.blend`
to retain its viewport setting.

## Colours and materials

The generator uses Base Builder's native UserData colour/material metadata,
not arbitrary Blender materials for in-game export.

**Default / keep on replace:** new signs use UserData 0. Replacing text retains
its stored generation palette. This does not preserve later individual panel recolours.

**Copy active NMS part:** select a native NMS part with the desired colour/material
and make it active, choose this option, then generate/apply. A control Empty or
ordinary Blender cube lacks the native metadata needed as a colour source.
When editing from a sign panel, that active panel can be the colour source.

You can also select the generated panels and use Base Builder's normal native
colour/material tools. Export reads their current per-part colours; rebuilding
uses the generation palette instead of reproducing arbitrary per-part edits.
Auto style switching retains that stored palette, ignoring unrelated sidebar colour drafts.

Use Material Preview or Rendered shading to inspect textures; Solid shading is
not a reliable texture preview.

## Save and export

### Keep an editable master

Save the **`.blend`**. It contains the parent controls and stored text settings.
After reopening, enable both add-ons, select a panel and use Edit NMS Text again.
Keep backups before major edits.

### Export native parts

1. Select a panel or control belonging to the required sign.
2. Click **Export Selected Text JSON** in NMS Text.
3. Choose a filename and save.

The file contains only that sign's managed parts, at their current world transforms
and with current native colour metadata. Other objects, control Empties and a
user-added backing are not included. Use your compatible Base Builder workflow
to combine/import those parts and transfer them to the game.

**JSON does not retain editable text settings.** Exporting and reimporting the
parts may preserve their appearance, but does not recreate generator metadata.
Keep the original `.blend` for future right-click text editing.

The generator never writes live game saves itself. Back up saves before using
external save tools. Blender tests do not prove in-game, console, upload-limit or
unmodded multiplayer compatibility.

Older v1.0 mixed-part signs remain exportable until explicitly rebuilt. New
generation/replacement uses the selected panel type. Opening a file does not silently replace
old geometry.

## Limits and worked examples

The live part total reflects the text/font being edited. Different styles and
characters have different part counts. The old 20-panels-per-letter cap is removed.

- **3,000 parts maximum per generation/replacement**, as a plugin safety guard.
- **2,000 input characters**, including spaces and newlines.
- Long text may reach the part limit first. Split it into separate signs.
- Making identical text physically smaller normally does not reduce its part count.

These guards do not represent current NMS base/upload limits.

### Centered two-line welcome

Type `WELCOME<br>TRAVELLERS` in the Text field.
Choose Center, height 5 and line gap 1.5. Generate.
Both lines share the same center anchor; their baselines are 6.5 units apart
before parent scaling.

### Change BAY 01 to BAY 02 later

Open the `.blend`, select one panel of BAY 01, right-click Edit NMS Text, change
Text to `BAY 02`, and click OK. Save and export a fresh JSON when needed.

### Compare styles on an existing sign

Click a panel, Select Parts, ensure Auto-switch is ON, and choose a new Font.
The sign regenerates in place. Ctrl-Z restores the previous version.

### Create another sign without altering this one

Deselect the current sign or turn auto-switch OFF. Set the new text/style and
cursor position, then Generate New Text. Each sign has its own collection/control.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| No NMS Text tab | Enable the add-on; hover over the 3D Viewport, press N, and look for its separate tab. Restart after updating. |
| Old file still shows Flat Panels | The new default applies to fresh settings, not a saved selection. Choose Storage Panels (back) explicitly if you want to convert the existing creation. |
| SVG declaration error | Update to v2.0. Ordinary external SVG declarations are accepted; custom entities/internal DTDs are still blocked. |
| SVG artwork has missing details | Increase the part limit or simplify the source. The cap overrides Accuracy; 100% is not an exact reproduction guarantee. Expand unsupported SVG features to paths. |
| SVG slider changes only the preview | Select the icon, load its settings, then choose Update Selected Icon. Generate New Icon creates another copy. |
| Enable NMS Base Builder first | Install/enable the dependency in this same Blender installation. |
| Missing builder_v2 | Update NMS Text to 1.6.1 or newer for the split Base Builder release. Charon Forge is optional. |
| Missing native panel assets | Repair/reinstall the compatible Base Builder, or Charon Forge if using HD mode. The generator will not invent substitute geometry. |
| Style changes but panels do not | Auto-switch must be ON; use Select Parts for exactly one sign, excluding unrelated objects. In the edit dialog, click OK. |
| Typed text did not update the sign | Only Font and Panel type auto-switch. Use Edit NMS Text or explicit Replace for other fields. |
| Dotted connection lines clutter the text | In Viewport Overlays > Objects, uncheck Relationship Lines. Keep the parent control intact. |
| No right-click Edit entry | Use Object Mode and select a panel still parented to a generated control. Plain imported JSON parts lack editable text metadata. |
| Original text group unavailable | Restart after updating from v1.3.0; the dialog bug was fixed in v1.3.1. Also check the control/metadata was not removed. |
| Generate unavailable | Check Object Mode, dependency, supported nonempty text, and the displayed validation message. |
| Unsupported characters | Use A-Z, 0-9, `- _ / \ ? ! \| [ ] + = : .`, spaces and `<br>` line breaks; remove unlisted punctuation/accented characters and other HTML tags. |
| Too many parts | Generate shorter sections or choose a style with a lower displayed count. |
| Stretched/mirrored/sheared export error | Restore positive uniform transforms, or regenerate a clean sign. |
| Copy active colour fails | Select a native NMS part with UserData, or use Default. |
| Sign is elsewhere or edge-on | Check the cursor/orientation and use View > Frame Selected. |
| Rear geometry or overlap detail visible | Check mounting depth; expose the front faces while burying the rear. Inspect material shading. |
| Text moved back after rebuilding | Move Select Control instead of moving its panels directly. |
| Accidentally made a second sign | Generate always adds. Undo the extra generation and use Edit on the original. |

For bug reports, include Blender/Base Builder/generator versions, the exact error,
text/style/settings, selection state, and whether it reproduces in a fresh file.
Share a minimal example rather than private saves or unrelated scene content.

## Update or uninstall

Save a backup `.blend`, install the new add-on ZIP, and restart Blender to reload
code, libraries and previews. Check the version label in NMS Text.

Style names retain stable internal IDs for older saved signs. Loading settings
may show a new label, but geometry changes only when generated/rebuilt. Keep older
files if you need a specific version's exact geometry.

To apply the optimized Vector recipes and spacing to an older sign, select one
panel, right-click **Edit NMS Text**, and confirm **OK**. This rebuild replaces
manual panel edits, so keep a backup of any hand-refined lettering first. Existing
signs are not automatically changed when you update the add-on. Likewise, enabling
or disabling Charon Forge does not rewrite saved signs; use Replace Selected Text
or confirm Edit NMS Text to refresh models from the current provider.
Base Builder can reuse native models already cached in a scene. To check its
standard-only appearance after disabling Forge, restart Blender with a fresh scene.

Disable/remove the generator through Preferences to uninstall. Native panels
remain usable with Base Builder; generator-specific editing requires the generator
again. Uninstalling this add-on does not remove or modify Base Builder.
