"""Validate the complete officer package in the repository or installed mod."""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import xml.etree.ElementTree as ET
from native_gladius import read_mesh, read_animation
from officer_asset_preservation import verify_preservation
from officer_unit_binding import gameplay_signature

PREFIX = 'Units/Foundry/ImperialOfficerGuardsman'


def validate(repository, mod=None):
    work = repository / 'model-workbench/Imperial-Officer/animation-production'
    data = (mod or repository / '2525618649') / 'Data'
    package = json.loads((work / 'package-verification.json').read_text())
    build = json.loads((work / 'animation-build.json').read_text())
    native = json.loads((work / 'animation-verification.json').read_text())
    visual = json.loads((work / 'visual-review.json').read_text())
    assert package['status'] == native['status'] == 'passed'
    assert len(package['runtime_files']) == 20 and len(build['clips']) == 14
    for relative, digest in package['runtime_files'].items():
        path = data / relative
        assert path.resolve().is_relative_to(data.resolve())
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, path
    mesh_path = data / ('Video/Meshes/' + PREFIX + '.msh')
    mesh = read_mesh(mesh_path.read_bytes())
    assert mesh['triangles'] == 892
    verify_preservation((work / 'accepted-model/Data/Video/Meshes' / (PREFIX + '.msh')).read_bytes(), mesh_path.read_bytes(), build)
    for suffix, expected in build['clips'].items():
        clip = read_animation((data / ('Video/Animations/' + PREFIX + suffix + '.anm')).read_bytes())
        assert clip['bones'] == mesh['bones'] and clip['frames'] == expected['frames'] and clip['fps'] == expected['fps'], suffix
    for role in ('Diffuse', 'Normal', 'SIC'):
        raw = (data / ('Video/Textures/' + PREFIX + role + '.dds')).read_bytes()
        assert raw[:4] == b'DDS ' and struct.unpack_from('<II', raw, 12) == (512, 512) and raw[84:88] == b'DXT5'
    unit = ET.parse(data / 'World/Units/AstraMilitarum/Officer.xml').getroot()
    assert gameplay_signature(unit) == gameplay_signature(ET.parse(work / 'Officer-before-integration.xml').getroot())
    model = unit.find('model/unit')
    assert model.get('mesh') == model.get('material') == PREFIX and model.get('idleAnimationCount') == '3'
    resources = set()
    for node in unit.iter():
        for key, value in node.attrib.items():
            if (key.endswith('Animation') or key == 'animation') and value.startswith(PREFIX):
                resources.update(value + str(i) for i in range(3)) if key == 'idleAnimation' else resources.add(value)
                if value == PREFIX + 'Move':
                    resources.update((value + 'Begin', value + 'End'))
    assert resources == {PREFIX + suffix for suffix in build['clips']}
    pistol = unit.find("weapons/weapon[@name='BoltPistol']/model/projectileWeapon")
    sword = unit.find("weapons/weapon[@name='PowerSword']/model/weapon")
    assert pistol.get('mesh') == 'Weapons/AstraMilitarum/PrimarisPsykerLaspistol'
    assert pistol.get('material') == 'Weapons/AstraMilitarum/WyrdvanePsykerLaspistol' and pistol.get('muzzleBone') == 'Muzzle0'
    assert sword.get('mesh') == sword.get('material') == 'Weapons/SpaceMarines/Chainsword'
    assert {pistol.get('bone'), sword.get('bone')} <= set(mesh['bones'])
    sweep = json.loads((work / 'full-animation-sweep.json').read_text())
    assert sweep['clip_count'] == 14 and {row['clip'] for row in sweep['clips']} == set(build['clips'])
    assert all(row['native_clip_sha256'] == build['clips'][row['clip']]['sha256'] for row in sweep['clips'])
    assert hashlib.sha256((work / 'motion-previews/Full-Animation-Sweep.gif').read_bytes()).hexdigest() == sweep['gif_sha256']
    if sweep.get('mp4_sha256'):
        assert hashlib.sha256((work / 'motion-previews/Full-Animation-Sweep.mp4').read_bytes()).hexdigest() == sweep['mp4_sha256']
    return {'status': 'passed', 'runtime_files': 20, 'native_clips': 14, 'body_triangles': 892,
            'maps': [512, 512], 'original_binds': 28, 'full_sweep_frames': sweep['frames'],
            'gameplay_preserved': True, 'user_animation_approval': visual.get('user_animation_approval', False),
            'runtime_root': str(data), 'live_engine_verified': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--mod', type=Path, help='Installed parent mod to validate against repository metadata')
    args = parser.parse_args()
    print(json.dumps(validate(args.repository, args.mod), indent=2))
