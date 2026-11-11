# City asset

Title: Ho Chi Minh City 2025 - Thành Phố Hồ Chí Minh

Author: Saigon 3D City (https://sketchfab.com/saigon3dcity)

Source: https://sketchfab.com/3d-models/ho-chi-minh-city-2025-thanh-pho-ho-chi-minh-10e6d7c014a141b4a4adec54729d0968

License as embedded in the supplied GLB: CC BY 4.0
https://creativecommons.org/licenses/by/4.0/

Changes for this demo: scene transforms baked, Y-up to Z-up conversion, translated
to origin and uniformly scaled to 200 simulation units horizontal extent,
exported to binary STL without textures. The original supplied GLB is retained.
Normalization is for demonstration and does not represent surveyed metres.

The current surface-delivery view additionally groups the original triangles by
height and normal orientation and assigns illustrative colours to those groups.
These colours are not semantic labels or photographic textures from the source.
The original city triangle geometry is preserved for collision and clearance
checks. A separate triangulated safety envelope is constructed above the city
for surface-following flight planning.

# Algorithm

Reference: Phan Thanh An, Tran Van Hoai, Vuong Ba Thinh,
The funnel tree algorithm for finding shortest paths on polyhedral surfaces.
DOI: https://doi.org/10.1080/02331934.2023.2241496

Python reimplementation prepared for this project. Local angle/cosine propagation
and clipping follow the paper's approach. For extracting the selected path, this
version unfolds the selected strip; it is not a reproduction of the paper's
entirely intrinsic reconstruction. Nonconvex handling concatenates subsource
paths at negative-curvature vertices, informed by the supplied mentor C++.
Experimental: passing the included small meshes does not establish full coverage
of nonconvex/open surfaces or the quadratic complexity bound for this implementation.
