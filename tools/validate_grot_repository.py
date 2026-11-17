"""Check the playable/neutral Grot trio, native files, and aggregate starting stats."""
import argparse
import copy
import hashlib
import json
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

from native_gladius import read_animation, read_mesh


BODY = 'Units/Foundry/GrotTrio'
WEAPONS = {
    'Grotter': ('Weapons/Foundry/GrotTrioPistol', 'Gunner_hand.R'),
    'Choppa': ('Weapons/Foundry/GrotTrioChoppa', 'Cutter_hand.R'),
}
ANIMATIONS = ('Idle', 'Move', 'MoveBegin', 'MoveEnd', 'Run', 'Ranged', 'Melee',
              'Hit', 'Die', 'Grenade', 'Construct')


def file_hash(path):
    raw = path.read_bytes()
    if path.suffix.lower() == '.xml':
        raw = raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    return hashlib.sha256(raw).hexdigest()


def gameplay_signature(unit):
    def node(n):
        return [n.tag, sorted(n.attrib.items()), (n.text or '').strip(),
                [node(c) for c in n if c.tag != 'model']]
    return hashlib.sha256(json.dumps(node(unit), separators=(',', ':')).encode()).hexdigest()


def check_unit(path, baseline, body, attachments):
    unit = ET.parse(path).getroot()
    group = unit.find('group')
    assert group.get('size') == group.get('rowSize') == '1', path
    model = unit.find('model/unit')
    assert model.get('mesh') == model.get('material') == BODY and model.get('scale') == '1 1 1', path
    assert model.get('bloodBone') == 'Gunner_chest' and model.get('bloodBone') in body['bones']
    prior_count = int(baseline['group']['size'])
    health = unit.find('modifiers/modifier/effects/hitpointsMax')
    assert float(health.get('base')) == float(baseline['hp_per_member']) * prior_count, path
    slots = {weapon.get('name'): weapon for weapon in unit.findall('weapons/weapon')}
    assert set(slots) == {*WEAPONS, 'Stikkbomb'}
    assert all(int(w.get('count')) == prior_count for w in slots.values()), path
    for name, (mesh_name, bone) in WEAPONS.items():
        m = slots[name].find('model/*')
        assert (m.get('mesh'), m.get('material'), m.get('bone')) == (mesh_name, BODY, bone), path
        assert bone in body['bones'] and mesh_name in attachments, path
    muzzle = slots['Grotter'].find('model/projectileWeapon').get('muzzleBone')
    assert muzzle == '.Muzzle' and muzzle in attachments[WEAPONS['Grotter'][0]]['bones']
    grenade = slots['Stikkbomb'].find('model/grenadeWeapon').get('muzzleBone')
    assert grenade == 'Gunner_hand.L' and grenade in body['bones']
    assert model.get('idleAnimation') == BODY + 'Idle' and model.get('idleAnimationCount') == '1'
    for el in unit.iter():
        for key, value in el.attrib.items():
            if 'animation' in key.lower() and value.startswith('Units/'):
                assert value in {BODY + s for s in ANIMATIONS}, (path, value)

    # Reconstruct only the intentional group, HP, and weapon-count changes. Its signature
    # must match the previous unit including costs, actions, upgrades, and traits.
    prior = copy.deepcopy(unit)
    prior.find('group').attrib.update(baseline['group'])
    prior.find('modifiers/modifier/effects/hitpointsMax').set('base', baseline['hp_per_member'])
    for w in prior.findall('weapons/weapon'):
        del w.attrib['count']
    assert gameplay_signature(prior) == baseline['prior_gameplay_signature'], path
    assert gameplay_signature(unit) == baseline['gameplay_signature'], path


def check_textures(video):
    material = ET.parse(video / 'Materials' / (BODY + '.xml')).getroot()
    names = [node.get('name') for node in material.findall('textures/texture')]
    assert names == [BODY + suffix for suffix in ('Diffuse', 'Normal', 'SIC')] + ['ShadowMapColor']
    for suffix, compression in (('Diffuse', b'DXT5'), ('Normal', b'DXT1'), ('SIC', b'DXT1')):
        raw = (video / 'Textures' / (BODY + suffix + '.dds')).read_bytes()
        assert raw[:4] == b'DDS ' and raw[84:88] == compression
        assert struct.unpack_from('<II', raw, 12) == (2048, 2048)
        assert struct.unpack_from('<I', raw, 28)[0] == 12
        block = 16 if compression == b'DXT5' else 8
        expected_bytes = sum(((max(1, 2048 >> m) + 3) // 4)**2 * block for m in range(12))
        assert len(raw) == 128 + expected_bytes, suffix


def validate(root):
    manifest = json.loads((root / 'docs/grot/manifest.json').read_text())
    for category in ('runtime_files', 'editable_sources', 'verification_files'):
        for name, expected in manifest[category].items():
            assert file_hash(root / name) == expected, name
    video = root / '3038342810/Data/Video'
    def mesh(name):
        return read_mesh((video / 'Meshes' / (name + '.msh')).read_bytes())
    body = mesh(BODY)
    attachments = {name: mesh(name) for name, _ in WEAPONS.values()}
    assert len(body['bones']) == 51 and len(set(body['bones'])) == 51
    for role in ('Gunner', 'Cutter', 'Mek'):
        assert sum(b.startswith(role + '_') for b in body['bones']) == 17
    triangles = body['triangles'] + sum(w['triangles'] for w in attachments.values())
    assert triangles == manifest['total_triangles'] == 4486
    check_textures(video)
    for suffix in ANIMATIONS:
        anim = read_animation((video / 'Animations' / (BODY + suffix + '.anm')).read_bytes())
        assert anim['bones'] == body['bones'] and anim['fps'] == 24 and anim['frames'] > 1, suffix
    native_report = json.loads((root / manifest["native_verification"]).read_text())
    assert native_report["status"] == "PASS" and not native_report["failures"]
    assert native_report["max_world_vertex_error"] < .002
    assert native_report["max_socket_position_error"] < .002
    assert native_report["max_socket_axis_error_degrees"] < .01
    assert native_report["source_sha256"] == manifest["editable_sources"]["model-workbench/Grot-Mob/Trio/Grot-Trio.blend"]
    assert native_report["frames_checked"] == sum(e["frames"] for e in native_report["events"].values())
    assert set(native_report["events"]) == set(ANIMATIONS)
    workbench = 'model-workbench/Grot-Mob/Trio/'
    review = json.loads((root / workbench / 'glb-validation.json').read_text())
    assert review['source_sha256'] == native_report['source_sha256']
    assert review['glb_sha256'] == manifest['editable_sources'][workbench + 'Grot-Trio.glb']
    assert len(manifest['units']) == 4
    for name, baseline in manifest['units'].items():
        check_unit(root / name, baseline, body, attachments)
    return {'status':'passed', 'units':4, 'figures_per_unit':3, 'engine_members_per_unit':1,
            'triangles':triangles, 'body_bones':51, 'native_clips':len(ANIMATIONS),
            'starting_hp_and_weapon_copies_preserved':True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, default=Path(__file__).resolve().parents[1])
    print(json.dumps(validate(parser.parse_args().repository), indent=2))
