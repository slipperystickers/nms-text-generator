NMScribe 2.2.12 improves SVG import and recovery for traced artwork.

- Round stroke joins no longer multiply small SVG files into hundreds of thousands of unnecessary points. Both supplied Heart Pirates traces now reach Simplify & Import.
- Recoverable import/fitting failures attempt a bounded local feature trace. Simplify & Import accepts the recovered artwork; the source file stays unchanged.
- Rebuild SVG Features creates fresh paths from visible outlines and cutouts. Solid colour matching is preserved when enabled. Optional line strengthening can help thin monochrome artwork; it changes line weight and may narrow gaps.
- Rebuilt imports retain their original SVG in the saved icon settings and identify the rebuilt preview. Review the preview before generating parts.
- The sidebar shows the actual failure and offers recovery controls. A failed replacement preserves the previously loaded icon and its preview.
- Thin traces avoid a fitting fallback that could introduce broad wedges outside the intended lines. Very thin artwork still needs more parts and may have low coverage at small budgets.

Recovery is approximate and bounded. Bitmap images, text that has not been converted to paths, stylesheets, clipping, masks, and filters still need an appropriate plain-path export; recovery does not guess their appearance or fetch external files.

Includes the existing 2.2.11 local error logging and reviewable online report prompt with Discord/anonymous choice and screenshot/video attachments.
