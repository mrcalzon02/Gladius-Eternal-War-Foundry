# Imperial Guardsman Officer

This is the accepted Guardsman-based officer with a complete fitted animation
set, integrated into the existing Penal Legion Officer slot in mod 2525618649.
The original unit rules, stats, costs, abilities and weapon definitions remain.

The original Guardsman body is 894 triangles; the officer is 892. Diffuse,
Normal and SIC are each 512 x 512, legacy DXT5 DDS. Neutral gray/black armor uses
the existing SIC blue player-color mask. Positions, topology, UVs, normals,
tangents, materials, textures and all 28 original bind frames are preserved
from the accepted model. Two existing weapon sockets remain appended.

Animation preparation refines sleeve, collar, knee and waist weights to remove
finger-driven cloth spikes and hard joint seams. This adds no triangles.
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

| Native suffix | Seconds | Performance |
|---|---:|---|
| Idle0 | 2.500 | Forward-ready breathing loop |
| Idle1 | 2.500 | Ready stance, scan left and return |
| Idle2 | 2.500 | Ready stance, scan right and return |
| Move | 0.667 | Native officer gait with fitted forward-ready arms |
| MoveBegin | 0.333 | Ready-to-walk transition |
| MoveEnd | 0.333 | Walk-to-ready transition |
| Attack | 3.000 | One-handed laspistol aim, seven timed recoil pulses, recovery |
| Melee | 1.500 | Chainsword anticipation, overhead cut, follow-through, recovery |
| MeleeDefense | 1.500 | Raised chainsword parry and return |
| Charge | 1.500 | Native charge stance with forward chainsword threat |
| ChargeDefense | 1.500 | Native brace with raised chainsword guard |
| Grenade | 1.167 | Overhand grenade throw with timed forward release and recovery |
| Shout | 2.000 | Officer command gesture and recovery |
| Die | 1.200 | Native officer fall retimed to 1.2 seconds |

Ready, aiming, recoil, sword cuts, parries, command and throwing motions are
authored for this officer. The existing game gait, charge and fall provide the
movement foundation and retain their attribution. This is an adaptation of
third-party game assets, not a claim of entirely original animation ownership.

Seven pistol recoil pulses match the existing 0.35-second firing interval,
starting at 0.40 seconds. Sword impact occurs at 0.52 seconds inside the configured
0.30–0.70 swing window. Grenade release stays at the existing 0.90-second event.
The grenade action retains the game's existing held-weapon behavior.

## Editable source and verification

`model-workbench/Imperial-Officer/animation-production/Officer-Animations.blend`
contains the packed editable parts and 14 named native animation actions.
`Officer-Native-Animation-Review.blend` is independently imported from the actual
MSH/DDS/XML/ANM export. `accepted-model/` preserves the accepted model and motion
references needed to reproduce this contribution without the rejected studies.

`animation-verification.json` records every native sample plus intermediate
samples through the fastest attacks, grip tracking, physical muzzle direction,
limb lengths, ground contact, loop closure, mesh stretching and weapon clearance.
Rendered stills and motion previews come from the native export.

This is local repository integration. No files are installed into Gladius and
nothing is pushed or published. Live engine playback and combat remain untested.
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
