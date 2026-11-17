"""Prepare/review a scoped local checkout update, then apply exact hashed files."""
from pathlib import Path
import argparse,json,hashlib,shutil,xml.etree.ElementTree as E
from officer_unit_binding import gameplay_signature

R=Path(__file__).resolve().parents[1];A=R/'model-workbench/Imperial-Officer/animation-production';D=R/'assets/imperial-officer-animated/Data';P=R/'publication/imperial-officer-animated';PAYLOAD=P/'payload'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None

def prepare(target):
    report=json.loads((A/'animation-verification.json').read_text());package=json.loads((A/'package-verification.json').read_text());assert report['status']==package['status']=='passed'
    unit=target/'2525618649/Data/World/Units/AstraMilitarum/Officer.xml';prior=A/'Officer-before-integration.xml';assert sha(unit)==sha(prior),'Existing Officer changed; rebase the visual binding before applying'
    assert gameplay_signature(E.parse(unit).getroot())==gameplay_signature(E.parse(D/'World/Units/AstraMilitarum/Officer.xml').getroot())
    P.mkdir(parents=True,exist_ok=True);selected={}
    def add(source,relative):
        selected[relative]=source
    for rel,digest in package['runtime_files'].items():assert sha(D/rel)==digest;add(D/rel,'2525618649/Data/'+rel)
    for rel in ['Officer-Animations.blend','Officer-Native-Animation-Review.blend','animation-build.json','animation-verification.json','package-verification.json','pistol-frame.json','Officer-before-integration.xml','README.md','visual-review.json','ground-contact.json','motion-preview-hashes.json']:
        source=A/rel;assert source.is_file(),source;add(source,source.relative_to(R).as_posix())
    for folder in ['accepted-model','native-previews','motion-previews']:
        for source in (A/folder).rglob('*'):
            if source.is_file() and source.suffix in ('.blend','.json','.dds','.xml','.msh','.anm','.txt','.png','.gif','.md'):add(source,source.relative_to(R).as_posix())
    for name in ['build_officer_animations.py','officer_animation.py','officer_skinning.py','officer_unit_binding.py','verify_officer_animations.py','officer_triangle_intersections.py','render_officer_motion.py','render_officer_comparison.py','inspect_officer_death_ground.py','encode_officer_previews.py','package_officer_animations.py','prepare_officer_integration.py','native_gladius.py']:
        add(R/'tools'/name,'tools/'+name)
    for rel in ['references/import_gladius.py','docs/IMPERIAL_GUARDSMAN_OFFICER.md','model-workbench/Imperial-Officer/CURRENT_LOCAL_CANDIDATE.json','game-ready/Imperial-Guardsman-Officer.zip','assets/imperial-officer-animated/SOURCE_ATTRIBUTION.txt']:
        add(R/rel,rel)
    readme=(target/'README.md').read_text(encoding='utf-8');marker='## Imperial Guardsman officer'
    assert marker not in readme,'Officer README section already exists; review before replacing'
    readme+='\n\n'+marker+'\n\nThe accepted 892-triangle Guardsman-based officer now occupies the existing\nPenal Legion Officer slot, with 512-square masked textures and 14 fitted native\nanimations. The existing laspistol and chainsword are reused. See [asset and\nanimation verification](docs/IMPERIAL_GUARDSMAN_OFFICER.md). Local native checks\npass; live engine playback remains untested.\n'
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
