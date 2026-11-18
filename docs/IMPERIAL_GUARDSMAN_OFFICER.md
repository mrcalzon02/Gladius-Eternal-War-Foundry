# Imperial Guardsman Officer

This is the accepted Guardsman-based officer with a complete fitted animation
set, integrated into the existing Penal Legion Officer slot in mod 2525618649.
The original unit rules, stats, costs, abilities and weapon definitions remain.

The original Guardsman body is 894 triangles; the officer is 892. Diffuse,
Normal and SIC are each 512 x 512, legacy DXT5 DDS. Neutral gray/black armor uses
the existing SIC blue player-color mask. Topology, UVs, materials, textures and all 28 original bind frames are preserved
from the accepted model. All positions, normals and tangents are unchanged,
including the accepted hands and their UVs. Two weapon sockets remain appended; the pistol
socket is fitted to the actual palm and thumb directions.

Arm motion uses two-bone IK with explicit elbow guides and the physical cuff as
the wrist joint. Wrist bend is limited to 16 degrees. Each forearm cross-section
follows one bone, with blends confined to the elbow and wrist. Both hands remain
rigid. Shoulder armor follows a bounded hinge from the chest without inheriting wrist
roll. Armhole weights follow the mesh connectivity, with smooth transitions to
the native torso. Collar, knee and waist weights are also refined. This adds no triangles.
The connected 98-triangle anatomical chainsword hand and its dedicated UVs remain.

Weapons reuse the original game files, including their materials:

| Weapon | Mesh | Material | Triangles |
|---|---|---|---:|
| Laspistol | Weapons/AstraMilitarum/PrimarisPsykerLaspistol | Weapons/AstraMilitarum/WyrdvanePsykerLaspistol | 62 |
| Chainsword | Weapons/SpaceMarines/Chainsword | Weapons/SpaceMarines/Chainsword | 337 |

No replacement weapon meshes or materials are included. The pistol's physical
barrel-up direction is measured from its actual handle and muzzle, rather than
assuming that its local +Z axis means up. The muzzle stays forward and the grip
stays below the barrel through firing and recoil. A small constant grip fitting
offset clears the cuff. The chainsword projects forward in ready stance with
the cutting edge and bow underneath, gripped near the guard.

## Animation set

The complete fourteen-clip sweep is available as
[MP4](../model-workbench/Imperial-Officer/animation-production/motion-previews/Full-Animation-Sweep.mp4)
and [GIF](../model-workbench/Imperial-Officer/animation-production/motion-previews/Full-Animation-Sweep.gif).
Individual previews include all three idles and both movement transitions.

| Native suffix | Seconds | Performance |
|---|---:|---|
| Idle0 | 2.500 | Natural ready breathing |
| Idle1 | 2.500 | Ready scan left |
| Idle2 | 2.500 | Ready scan right |
| Move | 0.667 | Native Guardsman gait with chest-relative guided arms |
| MoveBegin | 0.333 | Enter walk |
| MoveEnd | 0.333 | Return to ready |
| Attack | 3.000 | Straight-wrist pistol aim, recoil and recovery |
| Melee | 1.500 | Guided chainsword overhead cut and recovery |
| MeleeDefense | 1.500 | Natural chainsword parry |
| Charge | 1.500 | Forward chainsword charge |
| ChargeDefense | 1.500 | Raised chainsword brace |
| Grenade | 1.167 | Guided overhand throw |
| Shout | 2.000 | Officer command gesture |
| Die | 1.200 | Supported fall with relaxed arms beside body |

Ready, aiming, recoil, sword cuts, parries, command and throwing motions are
authored for this officer. The actual Guardsman gait and the existing game fall provide the
movement foundation and retain their attribution. Charge is authored around the
new ready pose. This is an adaptation of
third-party game assets, not a claim of entirely original animation ownership.

Seven pistol recoil pulses match the existing 0.35-second firing interval,
starting at 0.40 seconds. Sword impact occurs at 0.58 seconds inside the configured
0.30–0.70 swing window. Grenade release stays at the existing 0.90-second event.
The grenade action retains the game's existing held-weapon behavior.

## Editable source and verification

`model-workbench/Imperial-Officer/animation-production/Officer-Animations.blend`
contains the packed editable parts and 14 named native animation actions.
`Officer-Native-Animation-Review.blend` is independently imported from the actual
MSH/DDS/XML/ANM export. `accepted-model/` preserves the accepted model and motion
references needed to reproduce this contribution without the rejected studies.

`animation-verification.json` records every native sample plus intermediate
half-frame samples through all actions, physical wrist angles, arm angular
velocity, coherent forearm rings, rigid hand deformation, grip tracking, physical
muzzle direction, limb lengths, ground contact, loop closure, mesh stretching and
weapon clearance. Passing numerical checks does not substitute for visual review
or imply user acceptance of the animation.
Rendered stills and motion previews come from the native export.

The user accepted the corrected officer and its fourteen native clips in
`cc39902` for integration into the existing mod, locally and on GitHub.
The runtime occupies the original Penal Legion Officer slot; no separate mod is
created. The full sweep and editable source are part of the repository.

Packaging itself does not install or upload files. The separate
[local installation receipt](officer/local-installation.json) records deployment;
its runtime hashes identify the same payload used by the repository and archive.
Use `tools/validate_officer_package.py` to check the repository or installed copy.
Use `tools/deploy_integrated_mods.py --mod 2525618649` to select Penal Legion
without changing the other parent packages. Steam Workshop uploads remain a
separate operation. Live engine playback and combat remain untested.
Private photographic references are excluded from the package.

Rebuild using the installed Blender and original game data:

```powershell
blender --factory-startup --background --python-exit-code 1 --python tools/build_officer_animations.py
blender --factory-startup --background --python-exit-code 1 --python tools/verify_officer_animations.py
blender --factory-startup --background --python-exit-code 1 --python tools/inspect_officer_death_ground.py
blender --factory-startup --background --python-exit-code 1 --python tools/render_officer_motion.py
python tools/package_officer_animations.py
```

The game data directory can be supplied with `GLADIUS_DATA` for verification.
No additional packages or game installation changes are required for native
build and verification. Preview GIF encoding uses an available Pillow installation.
