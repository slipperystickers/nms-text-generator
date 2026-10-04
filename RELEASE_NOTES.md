# NMScribe 2.2.8 - Colour Matching and Follow Curve

This update adds full-colour SVG matching and a simple way to place generated text or icons along Blender curves, with clearer controls and responsive previews.

## SVG colour matching

Enable **Match colours** to match solid SVG fills and strokes to the nearest available NMS palette colours. Use the **Colours** popout to choose your own matches. Matching is off by default, and station palettes are optional. Saved colour choices are preserved.

![Colour matching: two-colour industrial logo built with 296 panels](https://raw.githubusercontent.com/slipperystickers/nms-text-generator/v2.2.8/docs/screenshots/colour-match-2.2.8.png)

## Follow Curve

1. Generate your text or icon.
2. Select its panels or control together with one Blender curve; either can be active.
3. Click **Follow Curve**.

The existing native pieces and colours are retained. **Curve Options** offers fit to length, reverse direction, facing, and Restore Flat Layout. For circles and other closed curves, set **Around curve** in degrees and click Follow Curve: 90 degrees moves a quarter-turn, negative angles move the other way, and 0 resets the starting position. The angle survives saving and rebuilding.

![Straight lettering and circular text using Follow Curve](https://raw.githubusercontent.com/slipperystickers/nms-text-generator/v2.2.8/docs/screenshots/follow-curve-2.2.8.png)

## Preview and fitting improvements

- Animated preview activity with progress stages and elapsed time.
- Larger highlighted **GENERATE TEXT** and **GENERATE ICON** buttons, with compact options.
- Straighter flat edges, more consistent faceted curves, and final seam/gap repair.
- Solid backing and raised colour inlays where useful to reduce unnecessary colour-boundary parts.
- Fixed false stretched-text errors on Bezier circles and corrected their starting orientation. Native scale/shear validation remains enabled.

SVG fitting remains an approximation made from native parts. Fine detail, gradients and complex artwork may require simplification or a larger part budget; palette appearance also depends on materials and lighting.

## Install or update

Download **NMS_Text_Generator_2.2.8.zip** below, not GitHub's Source code ZIP. Save your Blender work, install the ZIP through **Edit > Preferences > Add-ons > Install from Disk**, then restart Blender. Open **NMS Text** in the viewport sidebar.

Base Builder is required; Charon Forge is optional. Existing creations are not rebuilt automatically. Save a copy before regenerating manually edited artwork. The complete offline guide is included in the ZIP and available as **NMScribe_Instructions.html**.

## Validation

Tested on Windows with Blender 5.1.2 / Base Builder 18.0.9 and Blender 5.2.2 LTS / stock Base Builder 6.5.2, with and without Charon Forge. Native checks cover colour matching, both panel types, circles, angle placement, export, undo/redo, save/reopen, and failed-update rollback. Checksums are in **SHA256SUMS.txt**. These Blender tests do not certify console or multiplayer behaviour.

By **FuriousFurby**, shared through **Corvette Class Builders (CCB)**. [CCB / Traveller Toolkit](https://discord.gg/arbW3DvM5y) · [User guide](https://github.com/slipperystickers/nms-text-generator/blob/v2.2.8/USER_GUIDE.md)
