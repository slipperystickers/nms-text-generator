NMScribe 2.2.14 makes Accuracy consistently control SVG contour detail while preserving responsive preview updates.

- The efficient shared-edge assembler is available at every accuracy setting. Lower settings no longer bypass it at a hidden 75% threshold.
- For supported faceted fits, lowering Accuracy removes contour vertices consistently. Budget retries cannot make a lower setting restore finer curves. Simplification stops before it would damage holes or separate features. Complex or unsafe contours retain the existing fallback fitter.
- All panels stay inside the selected faceted outline. Redundant rim panels are removed only while retaining interior coverage, islands and the native seam checks.
- Fit Details reports contour segments, fitted silhouette coverage and shape changes separately. Panel counts may vary slightly with rectangle packing; the part limit is a ceiling, not a target.
- Slider changes remain debounced and processed in the background. Superseded jobs are cancelled and stale results are discarded.

Curves become connected straight facets. Tiny native rims and sharp tips still retain small differences. The SVG source is preserved, and the existing SVG recovery and rebuilding tools remain available.
