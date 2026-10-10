NMScribe 2.2.13 improves panel efficiency and visible coverage for high-accuracy traced SVGs.

- When a single-colour SVG reaches its part limit, NMScribe compares the existing contour fit with a compact fit that uses larger, overlapping panels. It selects the compact fit only when it saves at least 10% of parts, improves usable panel-face coverage, and keeps outline overdraw tightly bounded.
- Fit Details now shows estimated panel-face coverage and outline allowance for compact results. Accuracy remains a detail control, not a promise of pixel-perfect reproduction.
- On the supplied filled Heart Pirates SVG at 100% Accuracy and a 300-part limit, the fit uses 203 native Storage Panels instead of 300. At a 768-pixel sample, usable-face coverage increased from 95.9% to 98.1%; overdraw beyond the SVG increased from 1.7% to 3.1% of the artwork area. Blender 5.1.2 native generation and JSON export passed.

The compact fit is approximate. Inspect curved edges and any fine cutouts before updating existing artwork. The 2.2.12 SVG rebuild, source preservation, and error-reporting behavior remains available.
