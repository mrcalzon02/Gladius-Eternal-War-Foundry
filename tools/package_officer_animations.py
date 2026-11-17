"""Package the verified officer contribution; never install or publish it."""
from pathlib import Path
import json,hashlib,struct,zipfile,shutil

R=Path(__file__).resolve().parents[1];A=R/'model-workbench/Imperial-Officer/animation-production';O=R/'assets/imperial-officer-animated';D=O/'Data'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    build=json.loads((A/'animation-build.json').read_text());review=json.loads((A/'animation-verification.json').read_text())
    assert review['status']=='passed' and review['clips_tested']==14
    ground=json.loads((A/'ground-contact.json').read_text());assert ground['status']=='passed' and ground['native_death_sha256']==build['clips']['Die']['sha256']
    assert review['source_blend_sha256']==sha(A/'Officer-Animations.blend')
    assert review['native_review_blend_sha256']==sha(A/'Officer-Native-Animation-Review.blend')
    assert review['mesh_sha256']==sha(D/'Video/Meshes/Units/Foundry/ImperialOfficerGuardsman.msh')
    accepted=(A/'accepted-model/Data/Video/Meshes/Units/Foundry/ImperialOfficerGuardsman.msh').read_bytes();final=(D/'Video/Meshes/Units/Foundry/ImperialOfficerGuardsman.msh').read_bytes()
    at=8
    for _ in range(final[7]):at=final.index(0,at)+65
    at+=111;count=final[at];at+=1
    for _ in range(count):at=final.index(0,at)+2
    size=struct.unpack_from('<I',final,at)[0];at+=4
    assert len(accepted)==len(final) and accepted[:at]==final[:at] and accepted[at+size*4:]==final[at+size*4:]
    for i in range(size//20):
        cursor=at+i*80;assert accepted[cursor:cursor+12]==final[cursor:cursor+12] and accepted[cursor+44:cursor+80]==final[cursor+44:cursor+80]
    for category in ['Video/Textures','Video/Materials']:
        for original in (A/'accepted-model/Data'/category).rglob('*'):
            if original.is_file():assert sha(original)==sha(D/original.relative_to(A/'accepted-model/Data'))
    for rel,digest in build['frozen_asset_sha256'].items():assert sha(D/rel)==digest,rel
    for suffix,row in build['clips'].items():assert sha(D/('Video/Animations/Units/Foundry/ImperialOfficerGuardsman'+suffix+'.anm'))==row['sha256']
    for path in D.rglob('*.dds'):
        raw=path.read_bytes();assert raw[:4]==b'DDS ' and struct.unpack_from('<II',raw,12)==(512,512) and raw[84:88]==b'DXT5',path
    assert len(list(D.rglob('*.msh')))==1 and len(list(D.rglob('*.anm')))==14
    attribution=A/'accepted-model/SOURCE_ATTRIBUTION.txt';shutil.copy2(attribution,O/'SOURCE_ATTRIBUTION.txt')
    text='''# Imperial Guardsman Officer

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
'''
    for suffix,row in build['clips'].items():text+=f"| {suffix} | {row['duration']:.3f} | {row['description']} |\n"
    text+='''
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
'''
    docs=R/'docs/IMPERIAL_GUARDSMAN_OFFICER.md';docs.parent.mkdir(exist_ok=True);docs.write_text(text,encoding='utf-8')
    (A/'README.md').write_text('# Officer animation workbench\n\nSee [asset, animation and validation notes](../../../docs/IMPERIAL_GUARDSMAN_OFFICER.md).\n\nOpen `Officer-Animations.blend` for editable parts and named actions. Open\n`Officer-Native-Animation-Review.blend` to inspect the exported asset.\nSelect the desired action in the Action Editor; NLA library tracks are muted.\nScene playback is 60 fps; native clips preserve their recorded sample rate.\n',encoding='utf-8')
    pointer={'source':'model-workbench/Imperial-Officer/animation-production/Officer-Animations.blend','runtime_review':'model-workbench/Imperial-Officer/animation-production/Officer-Native-Animation-Review.blend','runtime':'2525618649/Data/World/Units/AstraMilitarum/Officer.xml','body_triangles':892,'baseline_body_triangles':894,'textures':[512,512],'native_clips':14,'new_animation_performances_authored':True,'installed':False,'published':False}
    (A.parent/'CURRENT_LOCAL_CANDIDATE.json').write_text(json.dumps(pointer,indent=2))
    files={p.relative_to(D).as_posix():sha(p) for p in D.rglob('*') if p.is_file()};assert len(files)==20,len(files)
    package=R/'game-ready/Imperial-Guardsman-Officer.zip';package.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(package,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for relative in sorted(files):z.write(D/relative,'2525618649/Data/'+relative)
        z.write(attribution,'SOURCE_ATTRIBUTION.txt');z.writestr('README.md',text)
    with zipfile.ZipFile(package) as z:
        assert z.testzip() is None
        for relative,digest in files.items():assert hashlib.sha256(z.read('2525618649/Data/'+relative)).hexdigest()==digest
    manifest={'status':'passed','runtime_files':files,'runtime_file_count':len(files),'body_triangles':892,'baseline_body_triangles':894,'texture_sizes':{'Diffuse':[512,512],'Normal':[512,512],'SIC':[512,512]},'weapons':build['attachments'],'native_clips':14,'native_poses_checked':review['poses_tested'],'source_sha256':sha(A/'Officer-Animations.blend'),'review_sha256':sha(A/'Officer-Native-Animation-Review.blend'),'archive':'game-ready/'+package.name,'archive_sha256':sha(package),'installed':False,'published':False,'live_engine_verified':False}
    (O/'PACKAGE_VERIFICATION.json').write_text(json.dumps(manifest,indent=2));(A/'package-verification.json').write_text(json.dumps(manifest,indent=2));print('OFFICER_PACKAGE_VERIFIED',len(files),'files',package)

if __name__=='__main__':main()
