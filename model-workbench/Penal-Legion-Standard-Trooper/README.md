# Penal Legion standard trooper

Approved modeling baseline, 2026-11-14. This is the canonical standard trooper for future Penal Legion modeling work.

Open `Standard-Trooper.blend` for the editable, rigged asset. The original Guardsman skeleton and 11 imported animation actions are retained. The model carries the native lasgun and a belt knife, with a bald head and unarmored ragged clothing.

The final minor cleanup adjusts only ear and outer-temple UV coordinates. Maximum UV displacement is 0.77 pixels at 512x512. User-edited vertex positions, topology and body UV coordinates are unchanged. The complete assembled model has 1,293 triangles. The shared head/body diffuse is `Standard-Trooper-Diffuse512.png`, at the native 512x512 resolution; images are packed into the blend as well.

`front.png`, `rear.png` and `head-closeup.png` are source renders. `Standard-Trooper-review.glb` is a static preview using the existing UVs and native texture dimensions. `export-*.png` show its independent reimport; its simplified materials approximate the original game shaders. The blend remains authoritative for materials, rig and animation editing.

`verification.json` binds the source and preview files to SHA-256 hashes, verifies geometry/body-UV preservation, and records the local cleanup and mesh counts. The original user-edited workbench file is preserved separately. This baseline does not attest a Gladius runtime exporter round trip or in-game animation validation, and no installed game or Workshop files were changed.

Provenance: local installed Gladius Guardsman geometry/UVs/rig/animations and lasgun; user-edited head topology; locally authored clothing and belt knife; repainted skin baked into native-size atlas. Keep this package local to the mod workflow with its provenance.
