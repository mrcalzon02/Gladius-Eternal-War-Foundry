"""Check weapon attachment names against local Gladius mesh bone tables.

Read-only: does not alter meshes or attest visual alignment. MSH1.0 bone tables
with fewer than 128 entries and Proxy Studios mesh XML are supported.
"""
import argparse
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import struct
import xml.etree.ElementTree as ET


def read_bones(path):
    if path.suffix == '.xml':
        return {bone.attrib['name'] for bone in ET.parse(path).getroot().findall('bone')}
    data = path.read_bytes()
    if len(data) < 8 or data[:7] != b'MSH1.0\0' or data[7] >= 128:
        raise ValueError(f'Unsupported mesh bone table: {path}')
    position, names = 8, set()
    try:
        for _ in range(data[7]):
            end = data.index(0, position)
            name = data[position:end].decode('utf-8')
            if not name or len(name) > 255 or name in names:
                raise ValueError('Invalid or duplicate bone name')
            matrix = struct.unpack_from('<16f', data, end + 1)
            if not all(math.isfinite(value) for value in matrix):
                raise ValueError('Non-finite bone matrix')
            names.add(name)
            position = end + 65
    except (UnicodeDecodeError, struct.error, ValueError) as error:
        raise ValueError(f'Invalid mesh bone table: {path}: {error}') from error
    return names


def audit(repo, game_data, mods):
    errors, reviews, inputs = [], [], {}
    checked = 0
    # Official examples establish which body/weapon/socket combinations are used
    # by the shipped game. A new combination needs review, not automatic repair.
    canonical = set()
    for path in (game_data / 'World/Units').rglob('*.xml'):
        root = ET.parse(path).getroot()
        body = root.find('./model/*')
        if body is not None:
            for node in root.findall('./weapons/weapon/model/*'):
                if node.get('mesh'):
                    canonical.add((body.get('mesh'), node.get('mesh'), node.get('bone')))

    for mod in mods:
        data = repo / mod / 'Data'
        if not (data / 'World/Units').is_dir():
            raise ValueError(f'Mod has no unit definitions: {mod}')

        @lru_cache(maxsize=None)
        def mesh_bones(name):
            for base in (data, game_data):
                for suffix in ('.xml', '.msh'):
                    path = base / 'Video/Meshes' / (name + suffix)
                    if path.is_file():
                        label = ('mod/' + mod if base == data else 'game')
                        inputs[label + '/' + path.relative_to(base).as_posix()] = hashlib.sha256(
                            path.read_bytes()).hexdigest()
                        return read_bones(path)
            raise ValueError(f'Mesh not found: {name}')

        for path in sorted((data / 'World/Units').rglob('*.xml')):
            root = ET.parse(path).getroot()
            body = root.find('./model/*')
            if body is None or not body.get('mesh'):
                continue
            relative = path.relative_to(repo).as_posix()
            inputs[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            checked += 1
            try:
                body_bones = mesh_bones(body.get('mesh'))
                for weapon in root.findall('./weapons/weapon'):
                    for node in weapon.findall('./model/*'):
                        item = dict(path=relative, weapon=weapon.get('name'))
                        bone = node.get('bone')
                        if bone and bone not in body_bones:
                            errors.append(dict(item, code='missing_attachment_bone',
                                               bone=bone, body_mesh=body.get('mesh')))
                        own_bones = mesh_bones(node.get('mesh')) if node.get('mesh') else set()
                        muzzle = node.get('muzzleBone')
                        count = int(node.get('muzzleCount', '1'))
                        if muzzle:
                            available = body_bones | own_bones
                            # Multi-muzzle nodes use a prefix and zero-based suffixes.
                            valid = (muzzle in available or muzzle + '0' in available) if count == 1 else (
                                count > 0 and all(muzzle + str(i) in available for i in range(count)))
                            if not valid:
                                errors.append(dict(item, code='missing_muzzle_bone',
                                                   bone=muzzle, count=count))
                        combination = (body.get('mesh'), node.get('mesh'), bone)
                        if node.get('mesh') and combination not in canonical:
                            reviews.append(dict(item, code='custom_weapon_combination',
                                                body_mesh=body.get('mesh'),
                                                weapon_mesh=node.get('mesh'), bone=bone))
            except (ValueError, OSError, ET.ParseError) as error:
                errors.append(dict(path=relative, code='unreadable_mesh', error=str(error)))
    return dict(scope='Bone names only; pivots, grip, animation and in-game appearance unverified',
                units_checked=checked, input_sha256=inputs, errors=errors, reviews=reviews)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--game-data', required=True, type=Path)
    parser.add_argument('--mod', action='append')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    mods = args.mod or sorted(p.name for p in args.repo.iterdir() if p.is_dir() and p.name.isdigit())
    if not (args.game_data / 'World/Units').is_dir() or not mods or any(not m.isdigit() for m in mods):
        parser.error('Provide a valid game Data directory and numeric mod IDs')
    try:
        report = audit(args.repo, args.game_data, mods)
    except (ValueError, OSError, ET.ParseError) as error:
        parser.error(str(error))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f"{report['units_checked']} units; {len(report['errors'])} errors; "
          f"{len(report['reviews'])} custom combinations need visual review")
    for item in report['errors'] + report['reviews']:
        print(json.dumps(item))
    return 1 if report['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
