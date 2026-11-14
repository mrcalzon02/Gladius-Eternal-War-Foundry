# Squig Hunter — user-corrected appearance source

Canonical editable source: **Squig-Hunter.blend**. This is the user's corrected version approved for repository publication on 2026-11-14. Regenerated review artifacts use this exact file; the model was not rebuilt or overwritten.

Derived from Proper wagh! Workshop 3038342810, `Data/World/Units/Orks/SqigHunter.xml`: native OrkBoy body/rig, OrkBoy3 atlas, Slugga, CuztomChoppa and WarbossSquig. The source retains the existing squig and 15 body action clips. No gameplay or installed mod files changed.

## Current geometry

- Hair: four fitted curved ribbons, 144 triangles total, weighted to Head.
- Goggles: user-corrected shape, 8 triangles.
- Hunter including gun and choppa: 1,362 triangles.
- Existing squig: 845 triangles.
- Full static review assembly: 2,207 triangles.

Textures are packed in the Blender source. Loose texture images support inspection. `Squig-Hunter-review.glb` is a static inspection artifact, not a Gladius skeletal runtime export. `verification.json` binds the current source/export hashes and confirms readable textures, UV coverage, finite vertices and nondegenerate faces after independent GLB reimport. Previews were refreshed after the user's corrections.

## Delivery status

User approved this corrected appearance for commit/publication. In-engine material alpha handling, animation clearance and runtime export remain unverified. The original reference image, donor copies, intermediate studies and temporary files stay local and are not part of this publication.

Use the packed Blender file as the canonical source. `tools/export_squig_hunter_review.py` regenerates reviews without rebuilding or saving over the source. Historical procedural build scripts predate the user's edits and are intentionally excluded from this delivery.
