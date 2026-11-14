"""Validate the shipped sergeant assets without Blender or third-party modules."""
from pathlib import Path
import argparse,json,struct,xml.etree.ElementTree as ET
from native_gladius import read_mesh,read_animation

def validate(mod):
    data=mod/'Data';unit=ET.parse(data/'World/Units/AstraMilitarum/Sargent.xml').getroot();model=unit.find('model/unit')
    body=read_mesh((data/('Video/Meshes/'+model.get('mesh')+'.msh')).read_bytes())
    assert len(body['bones'])==28 and body['triangles']==954
    weapons={}
    for node in unit.findall('weapons/weapon/model/*'):
        if node.get('mesh','').startswith('Weapons/Foundry/'):
            mesh=read_mesh((data/('Video/Meshes/'+node.get('mesh')+'.msh')).read_bytes())
            assert node.get('bone') in body['bones']
            if node.get('muzzleBone'):assert node.get('muzzleBone') in mesh['bones']
            weapons[node.get('mesh')]=mesh['triangles']
    clips={}
    for suffix,expected in [('Idle',81),('Move',17),('MoveBegin',9),('MoveEnd',9),('Ranged',49),('Melee',61)]:
        clip=read_animation((data/('Video/Animations/Units/Foundry/VeteranSergeant'+suffix+'.anm')).read_bytes())
        assert clip['bones']==body['bones'] and clip['frames']==expected and clip['fps']==24
        clips[suffix]=clip['frames']
    for role in ('Diffuse','Normal','SIC'):
        raw=(data/('Video/Textures/Units/Foundry/VeteranSergeant'+role+'.dds')).read_bytes()
        assert raw[:4]==b'DDS ' and struct.unpack_from('<II',raw,12)==(1024,1024)
    attack=unit.find('actions/attack/model/action')
    assert attack.get('animation').endswith('Ranged') and attack.get('meleeAnimation').endswith('Melee')
    return dict(body_triangles=body['triangles'],body_bones=len(body['bones']),weapons=weapons,animation_frames=clips,status='passed')
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--mod',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(validate(args.mod),indent=2))
