# Accepted Grot replacement source

`Grot-Sneak.blend` is the accepted appearance source; `Grot-Animation-Work.blend`
is the fitted animated source, with Idle active and `Grot_Animation_rig` selected.
Select a `Grot - ...` action in the Action Editor, leaving library NLA tracks muted.
`Grot-Animated-review.glb` contains all eight portable skeletal clips.

The complete character is 1,540 triangles. Eyes are painted on the skin atlas;
36 outward snags follow curved gum arches. The mouth, throat and body are one
closed connected skin surface. The fitted animation skeleton has 19 bones.
Clips at 24 fps: Idle (49 frames), Snarl (33), Sneak (49), Run (25), Pistol fire
(49), Shank stab (41), Hit reaction (25), Death (49). Locomotion is in-place.

Native assets are integrated into `3038342810/Data`. See
[integration and validation notes](../../docs/GROT_REPLACEMENT.md).
Native MSH/ANM/DDS reimport checks pass; live game combat remains untested.
Packed textures make the Blender files directly editable. Original source
provenance/permissions still apply to the retained native slugga. Private design
references, donor game-file copies and rejected studies are not included here.
