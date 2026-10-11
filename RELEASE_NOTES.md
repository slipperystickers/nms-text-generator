NMScribe 2.2.13 fits SVGs to a shared faceted contour, reducing panel waste while retaining a continuous silhouette.

- Straight bands share larger panels. Every panel stays inside the chosen polygon outline, including its cutouts; individual panels cannot protrude beyond it.
- The alternative fit is accepted only when it saves at least 10% of parts, covers at least 99.5% of the faceted silhouette, retains at least the original fit's source coverage, and passes native seam and missing-interior checks. Otherwise NMScribe retains its regular contour fit.
- Fit Details separates coverage of the fitted silhouette from shape changes introduced by simplification. Accuracy still controls detail, while the part limit controls how much detail can fit.
- The supplied filled Heart Pirates SVG at 100% Accuracy and a 300-part limit uses 220 native Storage Panels, a reduction of 80 parts (27%). Sampled coverage of the faceted silhouette is 99.8%. The silhouette differs from the source across 4.3% of its painted area; this measures intentional faceting separately from gaps. Native Blender generation and JSON export passed.

Curves become connected straight facets. Tiny native rims and sharp tips still retain small differences. The SVG source is preserved, and the existing SVG recovery and rebuilding tools remain available.
