"""Package the verified officer contribution; never install or publish it."""
from pathlib import Path
import json,hashlib,struct,zipfile,shutil
from officer_asset_preservation import verify_preservation

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
    verify_preservation(accepted,final,build)
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
'''
    for suffix,row in build['clips'].items():text+=f"| {suffix} | {row['duration']:.3f} | {row['description']} |\n"
    text+='''
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
'''
    docs=R/'docs/IMPERIAL_GUARDSMAN_OFFICER.md';docs.parent.mkdir(exist_ok=True);docs.write_text(text,encoding='utf-8')
    (A/'README.md').write_text('# Officer animation workbench\n\nSee [asset, animation and validation notes](../../../docs/IMPERIAL_GUARDSMAN_OFFICER.md).\n\nOpen `Officer-Animations.blend` for editable parts and named actions. Open\n`Officer-Native-Animation-Review.blend` to inspect the exported asset.\nSelect the desired action in the Action Editor; NLA library tracks are muted.\nScene playback is 60 fps; native clips preserve their recorded sample rate.\n',encoding='utf-8')
    pointer={'source':'model-workbench/Imperial-Officer/animation-production/Officer-Animations.blend','runtime_review':'model-workbench/Imperial-Officer/animation-production/Officer-Native-Animation-Review.blend','runtime':'2525618649/Data/World/Units/AstraMilitarum/Officer.xml','body_triangles':892,'baseline_body_triangles':894,'textures':[512,512],'native_clips':14,'new_animation_performances_authored':True,'deployment_receipt':'docs/officer/local-installation.json'}
    (A.parent/'CURRENT_LOCAL_CANDIDATE.json').write_text(json.dumps(pointer,indent=2))
    files={p.relative_to(D).as_posix():sha(p) for p in D.rglob('*') if p.is_file()};assert len(files)==20,len(files)
    package=R/'game-ready/Imperial-Guardsman-Officer.zip';package.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(package,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for relative in sorted(files):z.write(D/relative,'2525618649/Data/'+relative)
        z.write(attribution,'SOURCE_ATTRIBUTION.txt')
        archive_text=text.replace('(../model-workbench/Imperial-Officer/animation-production/motion-previews/Full-Animation-Sweep.mp4)','(Full-Animation-Sweep.mp4)').replace('(../model-workbench/Imperial-Officer/animation-production/motion-previews/Full-Animation-Sweep.gif)','(https://github.com/mrcalzon02/Gladius-Eternal-War-Foundry/blob/main/model-workbench/Imperial-Officer/animation-production/motion-previews/Full-Animation-Sweep.gif)').replace('(officer/local-installation.json)','(https://github.com/mrcalzon02/Gladius-Eternal-War-Foundry/blob/main/docs/officer/local-installation.json)')
        z.writestr('README.md',archive_text)
        sweep=A/'motion-previews/Full-Animation-Sweep.mp4'
        if sweep.is_file():z.write(sweep,sweep.name)
        if (A/'full-animation-sweep.json').is_file():z.write(A/'full-animation-sweep.json','full-animation-sweep.json')
    with zipfile.ZipFile(package) as z:
        assert z.testzip() is None
        for relative,digest in files.items():assert hashlib.sha256(z.read('2525618649/Data/'+relative)).hexdigest()==digest
    manifest={'stage':'package validation; installation and GitHub sync are recorded separately','delivery_receipt':'docs/officer/local-installation.json','status':'passed','runtime_files':files,'runtime_file_count':len(files),'body_triangles':892,'baseline_body_triangles':894,'texture_sizes':{'Diffuse':[512,512],'Normal':[512,512],'SIC':[512,512]},'weapons':build['attachments'],'native_clips':14,'native_poses_checked':review['poses_tested'],'source_sha256':sha(A/'Officer-Animations.blend'),'review_sha256':sha(A/'Officer-Native-Animation-Review.blend'),'archive':'game-ready/'+package.name,'archive_sha256':sha(package),'installed':False,'published':False,'live_engine_verified':False}
    (O/'PACKAGE_VERIFICATION.json').write_text(json.dumps(manifest,indent=2));(A/'package-verification.json').write_text(json.dumps(manifest,indent=2));print('OFFICER_PACKAGE_VERIFIED',len(files),'files',package)

if __name__=='__main__':main()
