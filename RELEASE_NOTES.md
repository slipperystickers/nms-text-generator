NMScribe 2.2.16 fixes native panel generation with Base Builder Extended when the optional Detailed Proxy pack is not installed.

- NMScribe now passes the panel part ID to Base Builder and accepts the native proxy returned by its part factory. Text and SVG icons can use the standard proxy fallback without an incorrect missing-asset error.
- If Base Builder Extended is waiting for a Charon Forge compatibility choice, NMScribe shows a clear prompt to finish that choice first.
- Blender 5.2.2 compatibility was checked with stock Base Builder 6.5.2 and Charon Forge 0.1.2 enabled in both add-on enable orders; text, SVG panels, and native export passed. This stock builder supplies the standard proxies. Base Builder Extended 18.1.79 was checked separately with Charon Forge disabled, with and without the Detailed Proxy pack.
- This is a focused compatibility update to 2.2.15. It does not include decal development.

The previous 2.2.15 SVG-fitting improvements remain included.

- Nearby band edges share directions, and nearly square outside corners can become square enough for larger panels to fit. This avoids many small wedge and join fillers.
- Existing rectangular details retain their orientation. Movement is bounded by the accuracy setting and nearby feature clearance; holes and separate islands are checked after the change. Full accuracy keeps the previous contour. Complex or unsafe contours retain the existing fallback fitter.
- Every panel stays inside the selected contour. Native seam and interior coverage checks remain in place; the original SVG is preserved.
- The supplied Heart Pirates example uses 147 panels at 60% accuracy versus 187 at 100%, with 99.8% sampled coverage of the simplified silhouette. Some outer cap angles change visibly as part of that simplification.
- Fit Details reports contour segments, fitted silhouette coverage and shape changes separately. Panel counts may vary slightly with rectangle packing; the part limit is a ceiling, not a target.
- Slider changes remain debounced and processed in the background. Superseded jobs are cancelled and stale results are discarded.

Curves become connected straight facets. Reduced accuracy deliberately changes the outline and is not a promised percentage reduction in parts. Tiny native rims and sharp tips still retain small differences.
