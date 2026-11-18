"""Prepare/review a scoped local checkout update, then apply exact hashed files."""
from pathlib import Path
import argparse,json,hashlib,shutil,xml.etree.ElementTree as E
from officer_unit_binding import gameplay_signature

R=Path(__file__).resolve().parents[1];A=R/'model-workbench/Imperial-Officer/animation-production';D=R/'assets/imperial-officer-animated/Data';P=R/'publication/imperial-officer-animated';PAYLOAD=P/'payload'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None

def prepare(target):
    report=json.loads((A/'animation-verification.json').read_text());package=json.loads((A/'package-verification.json').read_text());assert report['status']==package['status']=='passed'
    visual=json.loads((A/'visual-review.json').read_text());build=json.loads((A/'animation-build.json').read_text())
    assert visual['status']=='assistant visual review passed for local native export'
    assert visual['mesh_sha256']==report['mesh_sha256'] and visual['animation_source_sha256']==report['source_blend_sha256']
    assert visual['native_clips']=={suffix:row['sha256'] for suffix,row in build['clips'].items()}
    for name,digest in visual['renders'].items():assert sha(A/'native-previews'/name)==digest,name
    for suffix,row in visual['motion_previews'].items():
        assert row['native_clip_sha256']==build['clips'][suffix]['sha256']
        assert sha(A/'motion-previews'/(suffix+'.gif'))==row['gif_sha256'],suffix
    unit=target/'2525618649/Data/World/Units/AstraMilitarum/Officer.xml';prior=A/'Officer-before-integration.xml'
    assert unit.is_file() and prior.is_file()
    assert gameplay_signature(E.parse(unit).getroot())==gameplay_signature(E.parse(D/'World/Units/AstraMilitarum/Officer.xml').getroot())
    P.mkdir(parents=True,exist_ok=True);selected={}
    def add(source,relative):
        selected[relative]=source
    for rel,digest in package['runtime_files'].items():assert sha(D/rel)==digest;add(D/rel,'2525618649/Data/'+rel)
    for rel in ['Officer-Animations.blend','Officer-Native-Animation-Review.blend','animation-build.json','animation-verification.json','package-verification.json','pistol-frame.json','hand-anatomy.json','REJECTED_ANIMATION_HISTORY.json','Officer-before-integration.xml','README.md','visual-review.json','ground-contact.json','motion-frames.json','motion-preview-hashes.json']:
        source=A/rel;assert source.is_file(),source;add(source,source.relative_to(R).as_posix())
    for folder in ['accepted-model','native-previews','motion-previews']:
        for source in (A/folder).rglob('*'):
            if source.is_file() and source.suffix in ('.blend','.json','.dds','.xml','.msh','.anm','.txt','.png','.gif','.md'):add(source,source.relative_to(R).as_posix())
    for name in ['build_officer_animations.py','build_officer_arm_rebuild.py','officer_arm_pose.py','officer_asset_preservation.py','officer_animation.py','officer_skinning.py','officer_unit_binding.py','verify_officer_animations.py','officer_triangle_intersections.py','render_officer_motion.py','render_officer_comparison.py','inspect_officer_death_ground.py','encode_officer_previews.py','package_officer_animations.py','prepare_officer_integration.py','native_gladius.py']:
        add(R/'tools'/name,'tools/'+name)
    for rel in ['references/import_gladius.py','docs/IMPERIAL_GUARDSMAN_OFFICER.md','model-workbench/Imperial-Officer/CURRENT_LOCAL_CANDIDATE.json','game-ready/Imperial-Guardsman-Officer.zip','assets/imperial-officer-animated/SOURCE_ATTRIBUTION.txt']:
        add(R/rel,rel)
    readme=(target/'README.md').read_text(encoding='utf-8');marker='## Imperial Guardsman officer'
    paragraph='The 892-triangle Guardsman-based officer occupies the existing Penal Legion\nOfficer slot, with 512-square masked textures and 14 native animations. Arm\nmotion uses guided elbows, physical wrist joints and coherent sleeve weights.\nThe existing laspistol and chainsword are reused. See [asset and animation\nverification](docs/IMPERIAL_GUARDSMAN_OFFICER.md). Local native checks and rendered\nreview are recorded; live engine playback remains untested.\n'
    if marker in readme:
        start=readme.index(marker);following=readme.find('\n## ',start+len(marker))
        readme=readme[:start]+marker+'\n\n'+paragraph+(readme[following:] if following>=0 else '')
    else:readme+='\n\n'+marker+'\n\n'+paragraph
    prepared_readme=P/'README.prepared.md';prepared_readme.write_text(readme,encoding='utf-8');add(prepared_readme,'README.md')
    items=[]
    for relative,source in sorted(selected.items()):
        digest=sha(source);assert digest,source;destination=target/relative
        if sha(destination)==digest:continue
        payload=PAYLOAD/relative;payload.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,payload)
        items.append({'path':relative,'sha256':digest,'previous_sha256':sha(destination),'bytes':source.stat().st_size})
    result={'status':'prepared; not applied','target':str(target.resolve()),'files':items,'file_count':len(items),'total_bytes':sum(i['bytes'] for i in items),'unit_gameplay_preserved':True,'installed':False,'published':False}
    (P/'integration-plan.json').write_text(json.dumps(result,indent=2));print('OFFICER_INTEGRATION_PREPARED',len(items),'files',result['total_bytes'],'bytes')

def apply(target):
    plan=json.loads((P/'integration-plan.json').read_text());assert Path(plan['target']).resolve()==target.resolve()
    for item in plan['files']:
        relative=Path(item['path']);destination=(target/relative).resolve();assert destination.is_relative_to(target.resolve()) and '.git' not in relative.parts
        assert sha(PAYLOAD/relative)==item['sha256'],relative
        assert sha(destination)==item['previous_sha256'],f'Concurrent change: {relative}'
    for item in plan['files']:
        relative=Path(item['path']);destination=target/relative;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(PAYLOAD/relative,destination);assert sha(destination)==item['sha256']
    plan['status']='applied to local checkout; commit pending';(P/'integration-result.json').write_text(json.dumps(plan,indent=2));print('OFFICER_LOCAL_CHECKOUT_INTEGRATED',len(plan['files']),'files')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--target',type=Path,required=True);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    (apply if args.apply else prepare)(args.target)
