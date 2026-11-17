# Rebuild the Grot trio

The input is `model-workbench/Grot-Mob/Grot-Mob.blend`. It contains the approved Mek, Gunner and Cutter meshes, individual rigs and packed paint maps. Assembly creates the combined 51-bone rig and 11 actions. Native export converts Blender forward −Y to Gladius forward +X and attaches the pistol and choppa to their respective hands.

Use Blender 4.3.2 with its glTF exporter. The separate atlas command uses Python 3 with NumPy, SciPy and a Pillow build that can write DXT1 and DXT5. The verified versions are NumPy 2.3.5, SciPy 1.17.0 and Pillow 13.0.0.

From the repository root, run these commands in Bash. The generated files go into a fresh temporary directory.

```bash
set -e
repo="$(pwd -P)"
scripts="$repo/model-workbench/Grot-Mob/Trio/build"
build_dir="$(mktemp -d)"
stage="$build_dir/stage"
data="$build_dir/Data"
export PYTHONDONTWRITEBYTECODE=1

blender -b "$repo/model-workbench/Grot-Mob/Grot-Mob.blend" \
  --python-exit-code 1 -P "$scripts/assemble.py" -- --out "$build_dir"

blender -b "$build_dir/Grot-Trio.blend" \
  --python-exit-code 1 -P "$scripts/export_trio.py" -- \
  --repo "$repo" --data "$data" --stage "$stage"

python3 "$scripts/atlas.py" "$stage" "$data/Video/Textures/Units/Foundry"

blender -b "$build_dir/Grot-Trio.blend" \
  --python-exit-code 1 -P "$scripts/verify_trio.py" -- \
  --data "$data" --stage "$stage"

echo "$build_dir"
```

Open `Grot-Trio.blend` for the editable rig and timeline, or `Grot-Trio.glb` for interchange. To export again after an edit, save the edited scene into the build directory and repeat the last three build commands.

`Data/Video` contains three meshes, eleven ANM clips, the material and three mipmapped DDS textures. The exporter reads the earlier Grot replacement meshes for the native header and muzzle convention. Existing unit definitions in `3038342810/Data/World` provide the gameplay bindings. The build commands leave these definitions in place.

`stage/verify.json` records the source SHA-256, decoded geometry and texture checks, ground contact, equipment clearance and muzzle alignment for the firing frames. A passing full build reports 365 frames and 4,486 triangles. The staged files can be inspected, copied individually for integration, or discarded together.
