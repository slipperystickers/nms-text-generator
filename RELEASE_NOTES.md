# NMScribe v2.0.1 — SVG import cleanup hotfix

Simple SVGs load normally. If an SVG has an overly detailed or difficult outline,
NMScribe asks **Simplify SVG?** Click **Simplify & Import** to retrace it with fewer
line segments, or **Cancel** to keep the current icon/settings. No outside SVG
editor is needed. Stroke overlaps are combined without cancelling each other.
Native panels still follow the resulting outline first, then fill its interior.

The sidebar reports when simplification is used. Outline recovery samples at 2048 pixels,
so extremely small details may be reduced. Accuracy and the panel limit still
control the final native-panel approximation. Unsupported effects, external
resources and unusually large/complex inputs remain restricted.

Repeated import/generation and accuracy adjustments reuse cleanup/preview work.
The original SVG is not rewritten. Existing icons are not rebuilt automatically.
Text mode, Storage/Flat panel choices and Base Builder compatibility are retained.
Neither Base Builder nor Charon Forge is modified; Charon Forge remains optional.

## Install or update

Save your Blender work. Install **NMS_Text_Generator_2.0.1.zip** through
**Edit > Preferences > Add-ons > Install from Disk**, then restart Blender.
Open **NMS Text > Icon / Sticker** and import the SVG again.

To rebuild an existing icon, select one of its panels, choose **Load Selected
Icon Settings**, then **Update Selected Icon**. Back up manual panel edits first.

The ZIP includes the complete offline **NMScribe_Instructions.html** guide.
