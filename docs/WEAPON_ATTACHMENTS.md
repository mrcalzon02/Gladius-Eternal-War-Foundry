# Attaching weapons to Gladius units

## Confirmed repair

Penal Legion's modified Guardsman and Sargent used `bone="LeftHand"` for their
Space Marine chainsword meshes. The actual Guardsman mesh bone table contains
`LeftHandBone`, not `LeftHand`. Both references now use `LeftHandBone`. No combat
statistics, weapon identities, meshes, materials, or animations were changed.

This corrects a missing attachment reference; final grip and animation fit still
require a rendered or in-game check. No changes were deployed to Workshop files.

## The three separate parts

1. **Character socket:** `bone` is the exact attachment name in the character
   mesh. It is model-specific: Guardsman uses `LeftHandBone` / `RightHandBone`,
   while Ork Boy uses `LeftHand` / `RightHand`. Do not copy names between rigs.
2. **Weapon model and pivot:** `mesh` selects the visible weapon and `material`
   its surface. The weapon must have a grip origin and orientation compatible
   with the character's attachment transform. A valid bone cannot compensate for
   an incompatible pivot or geometry scale.
3. **Firing origin and pose:** `muzzleBone` identifies the firing-effect origin.
   The shipped Guardsman lasgun mesh contains `GuardsmanLasgunMuzzle0`; the
   character body does not. Grenade examples instead use a character hand bone.
   Idle, movement, attack, and grenade animations must support the intended grip.

These two examples use verified names from installed meshes:

```xml
<!-- Chainsword follows the Guardsman model's left hand. -->
<weapon mesh="Weapons/SpaceMarines/Chainsword"
        material="Weapons/SpaceMarines/Chainsword"
        bone="LeftHandBone"/>

<!-- Shipped Guardsman lasgun attachment and firing origin. -->
<beamWeapon mesh="Weapons/AstraMilitarum/GuardsmanLasgun"
            material="Weapons/AstraMilitarum/GuardsmanLasgun"
            bone="RightHandBone"
            muzzleBone="GuardsmanLasgunMuzzle0"
            fireInterval="0.5"/>
```

Place the relevant node under `weapons/weapon/model` in the unit definition.
The outer `weapon name="..."` selects combat rules; changing its visual mesh does
not rename the combat weapon. For example, the modified Guardsman's logical
Bayonet currently displays a Space Marine chainsword. That existing choice was
preserved, rather than changing its damage rules during an attachment repair.

## Workflow for a new combination

1. Choose a working body/weapon/animation donor as a complete set. Inspect its
   unit XML and actual mesh bone names. Keep exact spelling and capitalization.
2. Connect `bone` to the target character's hand/socket. Copy the firing-origin
   name from the chosen weapon mesh, not from the old weapon's muzzle definition.
3. Preview the assembled unit through idle, walk, attack, and grenade animations.
   Check both hands, grip, clipping, barrel direction, muzzle flash, and scale.
4. If the bone is valid but the grip is displaced or rotated, adjust a mod-specific
   weapon mesh's grip/pivot relative to the attachment frame. Do not guess XML
   position/rotation attributes: this pass did not establish that arbitrary
   weapon-node offsets are supported by the installed engine.
5. If the support hand is wrong, use a compatible complete rig/animation set or
   author/retarget the animations. Attaching a rifle to one hand does not make the
   second hand automatically follow it. Do not swap animation filenames between
   different skeletons merely because some bone names match.
6. Export changed assets through the Proxy Studios workflow and reference new
   mod-specific paths. Re-check exported bone names: the installed
   `MeshExporter.py` exports armature bones only when they also occur in the
   mesh's vertex groups. Verify required sockets and muzzle bones survive export.
   Validate any exporter adaptation on a copy before using it for production.

The installed official exporters are under `Resources/Blender/ProxyStudios`.
Their header identifies Blender 2.90; compatibility with the locally installed
Blender 5.0 was not verified. The community
[Gladius import/export tool's own documentation](https://modtools.toffster.dev/tools/gladius-blender-import)
describes importing complete unit XML, meshes, and animation, and currently
requires Blender 5.1+. It is an inspection option, not a tool installed or run by
this repair. Use a compatible version before relying on its previews or exports.

## Remaining visual-review queue

| Unit | Combination | What remains to check |
|---|---|---|
| Penal Legion Guardsman | Guardsman body + Space Marine chainsword | Corrected bone; left-hand grip and rifle-pose collision |
| Penal Legion Sargent | Guardsman body + chainsword and Commissar bolt pistol | Corrected sword bone; both grips and rifle-based attack pose |
| Penal Legion Cadetunit | Commissar body + Guardsman lasgun | Valid socket; rifle fit and two-handed pose with Commissar animations |
| Proper wagh! SqigHunter | Ork Boy body + animated Warboss squig | Companion animation/root placement; not a handheld attachment |

These are five custom weapon combinations across four units, not five confirmed
visual defects. No speculative pivot, skeleton, or animation changes were made.

## Repeating the checks

```powershell
python -m unittest discover -s tools/tests -v
python tools/audit_weapon_attachments.py --game-data 'C:\Program Files (x86)\Steam\steamapps\common\Warhammer 40000 Gladius - Relics of War\Data' --report weapon-attachments.json
```

Results: 115 unit definitions checked; two missing socket references before the
repair, zero afterward; five combinations flagged for visual review. All 13
regression tests pass. The bone-table reader was also exercised against all 869
installed `.msh` files, with no read failures (maximum 67 bones).

The reader supports the observed MSH1.0 header and fewer than 128 bones, plus
Proxy Studios mesh XML. Unsupported/corrupt meshes cause errors rather than a
silent pass. Mod mesh sources take precedence over installed meshes. Reports
record consulted mesh and unit hashes without copying proprietary assets.

Scope is limited to direct character attachments and body/weapon muzzle names,
including numbered muzzle groups. Multi-level attachment hierarchies, animation
tracks, pivot orientation, scale, surface appearance, DLC entitlements, and actual
engine rendering are not attested by this check. Exit 0 means no errors in that
limited scope; review items still require visual acceptance.
