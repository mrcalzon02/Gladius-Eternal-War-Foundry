"""Prepare an explicit ripper publication in a clean current main checkout."""
from pathlib import Path
import argparse,json,re,shutil,subprocess,hashlib
from validate_ripper_repository import digest,gameplay_signature,validate
R=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--repository',type=Path,required=True)
repo=parser.parse_args().repository.resolve()
def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()
assert git('remote','get-url','origin')=='https://github.com/mrcalzon02/Gladius-Eternal-War-Foundry.git'
assert git('branch','--show-current')=='main' and not git('status','--porcelain')
assert git('rev-parse','HEAD')==git('rev-parse','origin/main')
base=git('rev-parse','HEAD');files=[]
def put(relative,source=None,text=None):
    dest=repo/relative;dest.parent.mkdir(parents=True,exist_ok=True)
    if source:shutil.copy2(source,dest)
    else:dest.write_text(text,encoding='utf-8')
    files.append(relative)
pkg=R/'game-ready/Foundry Ripper';work=R/'model-workbench/Ripper/low-poly'
manifest=json.loads((pkg/'MANIFEST.json').read_text())
for relative,sha in manifest['files'].items():assert hashlib.sha256((pkg/relative).read_bytes()).hexdigest()==sha,relative
for source in sorted((pkg/'Data/Video').rglob('*')):
    if source.is_file():put('2525618729/Data/Video/'+source.relative_to(pkg/'Data/Video').as_posix(),source)
relative='2525618729/Data/World/Units/Tyranids/Ripperswarm.xml'
raw=(repo/relative).read_text(encoding='utf-8');signature=gameplay_signature(raw)
def patch(pattern,changes):
    global raw
    match=re.search(pattern,raw,re.S);assert match,pattern
    part=match.group()
    for key,value in changes.items():
        part,count=re.subn(r'\b'+key+r'="[^"]*"',lambda m:key+'="'+value+'"',part,count=1);assert count,key
    raw=raw[:match.start()]+part+raw[match.end():]
patch(r'<unit\s+mesh=.*?/>',dict(mesh='Units/Foundry/Ripper',material='Units/Foundry/Ripper',scale='1 1 1',idleAnimation='Units/Foundry/RipperIdle',idleAnimationCount='1'))
patch(r'<attack>.*?</attack>',dict(chargeAnimation='Units/Foundry/RipperMove',meleeAnimation='Units/Foundry/RipperMelee'))
patch(r'<die>.*?</die>',dict(animation='Units/Foundry/RipperDie',animationCount='1'))
patch(r'<move>.*?</move>',dict(animation='Units/Foundry/RipperMove'))
assert gameplay_signature(raw)==signature
put(relative,text=raw)
for name in ['Ripper-LowPoly.blend','Ripper-LowPoly.glb','RipperDiffuse.png','RipperNormal.png','RipperRoughness.png','RipperSIC.png']:
    put('model-workbench/Ripper/low-poly/'+name,work/name)
for name in ['native-front.png','native-rear.png','native-side.png','native-mouth-rest.png','native-mouth-bite.png','native-bite.gif','gameplay-scale.png','teeth-proof.png']:
    put('docs/ripper/'+name,work/name)
put('docs/ripper/native-verification.json',pkg/'NATIVE_VERIFICATION.json')
for name in ['export_ripper_native.py','package_ripper.py','verify_ripper_native.py','ripper_mouth.py','render_ripper_motion.py','build_ripper_lowpoly.py','validate_ripper_repository.py','prepare_ripper_repository.py']:
    put('tools/'+name,R/'tools'/name)
put('model-workbench/Ripper/low-poly/README.md',text='''# Accepted ripper source, revision 4

Ripper-LowPoly.blend contains packed textures, the editable 450-triangle mesh,
34-bone rig, four skeletal clips and hidden frozen bake geometry. The GLB is
a portable textured preview. Six teeth share their roots with the gum surface.
Diffuse, normal, roughness and native SIC maps are 512 by 512 pixels.

See [integration, provenance and checks](../../../docs/RIPPER_MODEL.md).
''')
put('docs/RIPPER_MODEL.md',text='''# Ripper replacement

The accepted revision 4 replaces the scaled Hormagaunt appearance of Ripperswarm
in `2525618729/Data`. Existing stats, costs, traits, weapons, sounds, action
timings and the ten-member swarm formation are preserved.

The single creature is 450 triangles with a 34-bone rig, six connected teeth,
six legs and a whip tail. Native Idle (49), Move (25), Melee (25), Die (37),
MoveBegin (9) and MoveEnd (9) clips run at 24 fps. Locomotion is in place.
Diffuse, normal and SIC DDS maps are 512 square. The editable Blender source
packs all four source texture maps; GLB carries four clips and baked PBR maps.

Native MSH/ANM/DDS reimport passed, including 16 sampled poses, zero measured
tooth-root seam gap and source/native geometry agreement within 0.000004 units.
The repository validator checks file hashes, native formats, skin weights,
animation references and preservation of gameplay XML. Live game validation
remains pending; the asset is installed locally but has not been observed in
game. No Steam Workshop upload was performed.

Run `python tools/validate_ripper_repository.py` for the standalone checks.
To rebuild runtime files, open the published Blender source and run
`tools/export_ripper_native.py` with Blender's Python, then `tools/package_ripper.py`
with Pillow available. Export uses the existing shared Sergeant writer and
an installed Gladius Guardsman mesh for its native header. Optional full
retopology regeneration (`build_ripper_lowpoly.py`) requires the separately
supplied donor; the accepted packed source does not require that original file.
Native visual verification uses the community Gladius importer configured by
`verify_ripper_native.py`. Environment variables RIPPER_STAGE_DIR and
RIPPER_NATIVE_DIR may select alternate staging and package directories.

## Provenance

Adapted from the user-supplied *Chompy Xeno Bugs* sculpt by minipainting40k:
https://cults3d.com/en/3d-model/game/chompy-xeno-bugs . The listing displays
CULTS PU and No AI notices. Those source terms remain applicable; inclusion
here does not assert a new blanket license or third-party license clearance.
This derivative adds low-poly retopology, tail and connected teeth, new texture
atlases, a unified rig and new animation clips. Original donor downloads,
reference photographs, backups and unrelated local work are excluded.

![Native front](ripper/native-front.png)
![Native bite](ripper/native-bite.gif)
''')
readme=(repo/'README.md').read_text(encoding='utf-8')
put('README.md',text=readme+'\n## Ripper model\n\nThe Tyranid Ripperswarm now uses the accepted 450-triangle textured and rigged\ncreature. [Source, previews, provenance and validation](docs/RIPPER_MODEL.md).\nNative checks pass; live game validation is pending.\n')
receipt={k:manifest[k] for k in ('asset','source_author','source_url','source_license_as_displayed','derivative_work','triangles')}
receipt.update(base_commit=base,gameplay_signature=signature,published_files={p:digest(repo/p) for p in files},engine_in_game_verified=False)
put('docs/ripper/manifest.json',text=json.dumps(receipt,indent=2)+'\n')
result=validate(repo)
pub=R/'publication/ripper';pub.mkdir(parents=True,exist_ok=True)
(pub/'publish-files.json').write_text(json.dumps({'base':base,'files':files,'validation':result},indent=2))
print(json.dumps(result,indent=2))
