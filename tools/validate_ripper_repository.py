"""Validate the published ripper without Blender or a game installation."""
from pathlib import Path
import argparse, hashlib, json, struct, xml.etree.ElementTree as ET
from native_gladius import read_mesh, read_animation

def digest(path):
    raw=path.read_bytes()
    if path.suffix.lower() in {'.xml','.md','.py','.json'}: raw=raw.replace(b'\r\n',b'\n')
    return hashlib.sha256(raw).hexdigest()

def gameplay_signature(raw):
    root=ET.fromstring(raw)
    for node in root.iter():
        if node is root.find('model/unit'):
            for key in ('mesh','material','scale','idleAnimation','idleAnimationCount'):node.attrib.pop(key,None)
        if node.tag=='action':
            for key in ('animation','animationCount','chargeAnimation','meleeAnimation'):node.attrib.pop(key,None)
    def tree(node):return [node.tag,sorted(node.attrib.items()),(node.text or '').strip(),[tree(c) for c in node]]
    return hashlib.sha256(json.dumps(tree(root)).encode()).hexdigest()

def validate(repo):
    receipt=json.loads((repo/'docs/ripper/manifest.json').read_text())
    for relative,sha in receipt['published_files'].items():assert digest(repo/relative)==sha,relative
    unit=repo/'2525618729/Data/World/Units/Tyranids/Ripperswarm.xml'
    assert gameplay_signature(unit.read_bytes())==receipt['gameplay_signature']
    root=ET.parse(unit).getroot();model=root.find('model/unit')
    assert model.get('mesh')==model.get('material')=='Units/Foundry/Ripper'
    assert model.get('scale')=='1 1 1' and model.get('idleAnimationCount')=='1'
    data=repo/'2525618729/Data/Video'
    mesh=read_mesh((data/'Meshes/Units/Foundry/Ripper.msh').read_bytes())
    assert mesh['triangles']==450 and len(mesh['bones'])==34
    for name,frames in dict(Idle=49,Move=25,Melee=25,Die=37,MoveBegin=9,MoveEnd=9).items():
        clip=read_animation((data/f'Animations/Units/Foundry/Ripper{name}.anm').read_bytes())
        assert clip['bones']==mesh['bones'] and clip['frames']==frames and clip['fps']==24,name
    for node in root.iter():
        for key,value in node.attrib.items():
            if 'animation' in key.lower() and value.startswith('Units/Foundry/'):
                assert (data/('Animations/'+value+'.anm')).is_file(),value
    for node in ET.parse(data/'Materials/Units/Foundry/Ripper.xml').getroot().iter('texture'):
        name=node.get('name')
        if name=='ShadowMapColor':continue
        raw=(data/('Textures/'+name+'.dds')).read_bytes()
        assert raw[:4]==b'DDS ' and struct.unpack_from('<II',raw,12)==(512,512)
    native=json.loads((repo/'docs/ripper/native-verification.json').read_text())
    assert not native['failures'] and native['triangles']==450
    assert native['source_sha256']==hashlib.sha256((repo/'model-workbench/Ripper/low-poly/Ripper-LowPoly.blend').read_bytes()).hexdigest()
    assert native['source_checks']['connected_teeth']==6
    assert native['source_checks']['native_tooth_gum_seam_gap']==0
    return {'triangles':450,'bones':34,'animations':6,'verified_files':len(receipt['published_files']),'gameplay_preserved':True,'live_game_test':'pending'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--repository',type=Path,default=Path(__file__).resolve().parents[1])
    print(json.dumps(validate(parser.parse_args().repository),indent=2))
