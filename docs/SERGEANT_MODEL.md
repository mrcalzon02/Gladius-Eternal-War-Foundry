# Penal Legion veteran sergeant

The existing `AstraMilitarum/Sargent` unit in Workshop mod `2525618649` now uses
the approved pistol/chainsword model, the user-edited backpack and bedroll, and a
brown cigar with a red emissive tip. Recruitment, costs, statistics, traits and
weapon damage rules are retained.

The runtime assets are integrated directly into `2525618649/Data`. The original
hip-carried chainsword asset remains available in the repository history and tree,
but the sergeant now uses the new hand-fitted weapon mesh.

## Assets

- `Video/Meshes/Units/Foundry/VeteranSergeant.msh`: 954 triangles, 28 original
  named bones; body, backpack, bedroll and cigar combined in one skinned mesh.
- `Video/Meshes/Weapons/Foundry/VeteranChainsword.msh`: 337 triangles, fitted to
  `LeftHandBone` using the accepted weapon transform.
- `Video/Meshes/Weapons/Foundry/VeteranBoltPistol.msh`: 66 triangles, attached to
  `RightHandBone`, retaining `.Muzzle0` for firing effects.
- `Video/Textures/Units/Foundry/VeteranSergeant{Diffuse,Normal,SIC}.dds`: 1024px
  atlas. The original 512px body maps are preserved in one tile, including the
  native player-colour mask. Additional kit materials are baked into the rest.
- `Video/Materials/Units/Foundry/VeteranSergeant.xml`: native three-map material.

Editable source and review images are in
[`model-workbench/Sergeant-Headset-Variant`](../model-workbench/Sergeant-Headset-Variant/README.md).
The original Guardsman head and helmet are retained; headset conversion was not
part of this accepted version. Existing asset provenance/permissions apply.

## Animations

Native `ANM1.0` files run at 24 fps and retain the original named skeleton.

| Suffix | Frames | Use |
|---|---:|---|
| Idle | 81 | Weapon-ready idle loop |
| Move | 17 | Walking loop |
| MoveBegin / MoveEnd | 9 each | Blends between idle and walking |
| Ranged | 49 | Aim, three recoil shots, return to ready |
| Melee | 61 | Pullback, forward stepping lunge, diagonal chop and recovery |

The attack definition selects separate ranged and melee clips. Pistol effect
timing is aligned with the three recoil events. The melee swing window follows
the strike/follow-through. The lunge's knee bend directions follow the pelvis;
the earlier backwards knee flip is corrected. Original death and grenade clips
remain references to the compatible base-game Guardsman animations.

## Verification and limits

The actual exported `MSH`, `ANM` and `DDS` files were independently reimported and
rendered. Across 19 sampled idle, movement, firing and melee poses, maximum body
and weapon vertex differences from the source evaluated with engine-style linear
skinning were below 0.00002 world units. Preview helper bones are not exported.
The body atlas preserves native team colour and illumination channels.

Run the dependency-free package check from the repository root:

```powershell
python tools/validate_sergeant_package.py --mod 2525618649
```

`docs/sergeant/verification.json` records native export checks and file hashes.
This is export/asset validation; an actual Gladius combat session has not yet
been verified. The repository update does not publish anything to Steam Workshop.

## Rebuilding

With Blender 5.0 and a local Gladius installation, run
`tools/export_sergeant_game_assets.py` through Blender's background Python mode.
Then run `tools/package_sergeant.py` using Python with Pillow installed. The
scripts build a separate `game-ready/Foundry Veteran Sergeant` staging package.
They read the editable source and do not overwrite it. Copy validated staging
`Data` files into the numeric mod folder for a subsequent reviewed update.
