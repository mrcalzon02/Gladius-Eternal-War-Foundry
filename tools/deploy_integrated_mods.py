"""Synchronize tracked packages into Gladius's local Mods directory.

The default is a read-only plan. Workshop downloads are never a deployment
destination. This tool never uploads to Steam or removes Workshop downloads.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

IDS = ('2175959340', '2525618649', '2525618729', '3038342810', '3107612342', '3267312159', '3305007655')
ROOT_IMAGES = {'.png', '.jpg', '.jpeg', '.dds', '.tga', '.bmp'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def linked(path):
    return path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction())


def local_destination(path):
    require(not linked(path), 'The local Mods directory must not be a link or junction')
    path = path.resolve()
    require(not any(p.casefold() in {'steam', 'steamapps', 'workshop'} for p in path.parts),
            'Deploy to Documents/Proxy Studios/Gladius/Mods, never a Steam directory')
    return path


def package_names(repo, selected=IDS):
    catalog = json.loads((repo / 'catalog/mods.json').read_text(encoding='utf-8-sig'))
    names = {str(row['workshop_id']): row['title'] for row in catalog['mods']}
    result = {}
    for item in selected:
        name = names.get(item)
        require(isinstance(name, str) and bool(name.strip()) and name == name.strip()
                and name not in {'.', '..'} and not re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
                and not name.endswith(('.', ' '))
                and name.split('.')[0].upper() not in {'CON', 'PRN', 'AUX', 'NUL', *('COM' + str(n) for n in range(1, 10)), *('LPT' + str(n) for n in range(1, 10))},
                f'Unsafe/missing catalog title for {item}: {name!r}')
        require(name.casefold() not in {v.casefold() for v in result.values()}, f'Duplicate catalog title: {name}')
        result[item] = name
    return result


def inventory(folder):
    if not folder.exists():
        require(not linked(folder), f'Broken link: {folder}')
        return None
    require(folder.is_dir() and not linked(folder), f'Not a plain directory: {folder}')
    result = {}
    for path in sorted(folder.rglob('*')):
        require(not linked(path), f'Links and junctions are not supported: {path}')
        if path.is_file():
            require(path.resolve().is_relative_to(folder.resolve()), f'Escaping file: {path}')
            result[path.relative_to(folder).as_posix()] = digest(path)
    return result


def package_files(repo, selected, source_manifest=None):
    if source_manifest:
        manifest = json.loads(source_manifest.read_text(encoding='utf-8-sig'))
        rows = manifest.get('files') if isinstance(manifest, dict) else manifest
        require(isinstance(rows, list), 'Source manifest must be a list or {"files": [...]}')
        names = []
        for row in rows:
            name = row.get('path') if isinstance(row, dict) else row
            require(isinstance(name, str) and bool(name), 'Missing source manifest path')
            relative = Path(name)
            require(not relative.is_absolute() and not relative.drive and '..' not in relative.parts,
                    f'Invalid source manifest path: {name}')
            if isinstance(row, dict):
                source = repo / relative
                require(source.is_file() and source.resolve().is_relative_to(repo), f'Missing/escaping manifest file: {source}')
                require(not any(linked(p) for p in (source, *source.parents) if p.is_relative_to(repo)), f'Linked manifest source: {source}')
                raw = source.read_bytes()
                expected = row.get('git_blob_sha')
                require(isinstance(expected, str) and bool(re.fullmatch('[0-9a-fA-F]{40}', expected)),
                        f'Missing/invalid Git blob hash: {name}')
                actual = hashlib.sha1(b'blob ' + str(len(raw)).encode('ascii') + b'\0' + raw).hexdigest()
                require(actual == expected.lower(), f'Git blob hash mismatch: {name}')
                require(isinstance(row.get('size'), int) and row['size'] == len(raw), f'Manifest size mismatch: {name}')
            names.append(name)
    else:
        output = subprocess.check_output(['git', '-C', str(repo), 'ls-files', '-z', '--', *selected])
        names = output.decode('utf-8').split('\0')
    result = {item: {} for item in selected}
    for name in names:
        if not name:
            continue
        relative = Path(name)
        parts = relative.parts
        require(not relative.is_absolute() and not relative.drive and '..' not in parts, f'Invalid tracked path: {name}')
        if not parts or parts[0] not in selected:
            continue
        require(len(parts) >= 2, f'Invalid tracked path: {name}')
        in_data = len(parts) > 2 and parts[1] == 'Data'
        root_file = len(parts) == 2 and (parts[1] == 'SteamID.txt' or relative.suffix.lower() in ROOT_IMAGES)
        if not (in_data or root_file):
            continue
        source = repo / relative
        require(source.is_file() and source.resolve().is_relative_to(repo), f'Missing/escaping tracked file: {source}')
        require(not any(linked(p) for p in (source, *source.parents) if p.is_relative_to(repo)), f'Linked source: {source}')
        result[parts[0]][Path(*parts[1:]).as_posix()] = digest(source)
    for item, files in result.items():
        require(any(name.startswith('Data/') for name in files), f'No tracked runtime files for {item}')
        require('SteamID.txt' in files and (repo / item / 'SteamID.txt').read_text().strip() == item,
                f'Missing or incorrect tracked SteamID.txt for {item}')
        require('Preview.png' in files, f'Missing tracked Preview.png for {item}')
    return result


def updated_config(raw, mods, names):
    """Preserve entry order and XML formatting; disable matching Workshop copies."""
    text = raw.decode('utf-8-sig')
    root = ET.fromstring(text)
    entries = {entry.get('name'): entry for entry in root.findall('entry')}
    require('Mods/Installed' in entries and 'Mods/Disabled' in entries, 'Missing mod configuration entries')
    original_workshop = []

    def canonical(path):
        return path.replace('\\', '/').rstrip('/').casefold()

    installed_before = entries['Mods/Installed'].get('value', '').split(',')
    already_local = {item for item, title in names.items()
                     if any(canonical(path) in {canonical(str(mods / item)), canonical(str(mods / title))}
                            for path in installed_before)}

    def convert(path, disabled=False):
        value = canonical(path)
        for item, title in names.items():
            local = str(mods / title).replace('\\', '/')
            if value.endswith('/steamapps/workshop/content/489630/' + item):
                if path not in original_workshop:
                    original_workshop.append(path)
                if disabled and item in already_local:
                    return path
                return local
            if value in {canonical(str(mods / item)), canonical(local)}:
                return local
        return path

    values = {}
    for key in ('Mods/Installed', 'Mods/Disabled'):
        values[key] = []
        for path in entries[key].get('value', '').split(','):
            if path:
                mapped = convert(path, key == 'Mods/Disabled')
                if canonical(mapped) not in {canonical(p) for p in values[key]}:
                    values[key].append(mapped)
    for path in original_workshop:
        if canonical(path) not in {canonical(p) for p in values['Mods/Disabled']}:
            values['Mods/Disabled'].append(path)
    for key, paths in values.items():
        escaped = ','.join(paths).replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;')
        pattern = r'(<entry\s+name="' + re.escape(key) + r'"\s+value=")[^"]*("\s*/>)'
        text, count = re.subn(pattern, lambda match: match[1] + escaped + match[2], text)
        require(count == 1, f'Unexpected XML layout for {key}')
    ET.fromstring(text)
    return (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'') + text.encode('utf-8')


def ensure_game_closed():
    if os.name == 'nt':
        running = subprocess.check_output(['tasklist', '/FI', 'IMAGENAME eq Gladius.exe', '/FO', 'CSV'], text=True)
        require('"gladius.exe"' not in running.casefold(), 'Close Gladius before deployment')


def bounded_move(source, target, source_parent, target_parent):
    # Validate resolved absolute paths immediately before every directory move.
    require(source.resolve().parent == source_parent.resolve() and not linked(source), f'Unsafe move source: {source}')
    require(target.resolve().parent == target_parent.resolve() and not target.exists(), f'Unsafe move target: {target}')
    target_parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))


def deploy(repo, mods, backup, apply=False, mod_ids=IDS, config=None, source_manifest=None):
    repo = repo.resolve()
    mods = local_destination(mods)
    backup = backup.resolve()
    selected = tuple(dict.fromkeys(mod_ids))
    require(selected and set(selected) <= set(IDS), 'Select existing parent mod IDs')
    require(mods != repo and not mods.is_relative_to(repo / '.git'), 'Invalid Mods destination')
    require(backup != mods and not backup.is_relative_to(mods) and not mods.is_relative_to(backup),
            'Backup and Mods directories must not overlap')
    for item in selected:
        require(not mods.is_relative_to(repo / item) and not backup.is_relative_to(repo / item),
                'Deployment and backup must not overwrite a source package')
    names = package_names(repo, selected)
    config = config.resolve() if config else None
    config_bytes = config.read_bytes() if config else None
    new_config = updated_config(config_bytes, mods, names) if config else None
    packages = package_files(repo, selected, source_manifest)
    previous = {item: inventory(mods / names[item]) for item in selected}
    changed = [item for item in selected if packages[item] != previous[item]]
    summary = dict(destination=str(mods), local_folders=names, original_mods=list(selected), changed_mods=changed,
                   tracked_package_files=sum(map(len, packages.values())),
                   config_changes=new_config != config_bytes, workshop_modified=False, workshop_published=False)
    print(json.dumps(summary, indent=2))
    if not apply:
        return summary
    ensure_game_closed()
    require(not backup.exists(), 'Choose a new backup directory')
    backup.mkdir(parents=True)
    (backup / 'plan.json').write_text(json.dumps(dict(summary=summary, source=packages, previous=previous), indent=2))
    if config:
        (backup / 'Gladius.xml').write_bytes(config_bytes)
    stage = backup / 'staged'
    saved = backup / 'local-mods'
    failed = backup / 'failed-install'
    for item in changed:
        for relative, expected in packages[item].items():
            source = repo / item / relative
            require(digest(source) == expected, f'Source changed during deployment: {source}')
            target = stage / names[item] / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        require(inventory(stage / names[item]) == packages[item], f'Staging verification failed: {item}')
        require((stage / names[item] / 'SteamID.txt').read_text().strip() == item, f'Staged SteamID mismatch: {item}')
    require(package_files(repo, selected, source_manifest) == packages, 'Sources changed during staging')
    require(all(inventory(mods / names[item]) == previous[item] for item in selected), 'Installed files changed during staging')
    if config:
        require(config.read_bytes() == config_bytes, 'Configuration changed during staging')
    mods.mkdir(parents=True, exist_ok=True)
    installed = []
    archived = []
    config_written = False
    try:
        for item in changed:
            title = names[item]
            if previous[item] is not None:
                bounded_move(mods / title, saved / title, mods, saved)
                archived.append(item)
                require(inventory(saved / title) == previous[item], f'Backup verification failed: {item}')
            bounded_move(stage / title, mods / title, stage, mods)
            installed.append(item)
            require(inventory(mods / title) == packages[item], f'Installed verification failed: {item}')
        require(all(inventory(mods / names[item]) == packages[item] for item in selected), 'Final package verification failed')
        if config:
            require(config.read_bytes() == config_bytes, 'Configuration changed during installation')
            if new_config != config_bytes:
                config_written = True
                config.write_bytes(new_config)
                require(config.read_bytes() == new_config, 'Configuration verification failed')
    except Exception:
        if config_written:
            config.write_bytes(config_bytes)
        for item in reversed(installed):
            bounded_move(mods / names[item], failed / names[item], mods, failed)
        for item in reversed(archived):
            bounded_move(saved / names[item], mods / names[item], saved, mods)
        raise
    (backup / 'APPLIED.json').write_text(json.dumps(summary, indent=2))
    print('Local packages verified. No Workshop files were changed and no Steam upload was performed.')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--source-manifest', type=Path, help='Verified frozen-source relative file list; otherwise use git ls-files')
    parser.add_argument('--mods', type=Path, required=True, help='Documents/Proxy Studios/Gladius/Mods')
    parser.add_argument('--config', type=Path, help='Gladius.xml: remap selected mod paths and disable their Workshop copies')
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--mod', action='append', choices=IDS, help='Select one parent; repeat to select several. Defaults to all seven.')
    args = parser.parse_args()
    deploy(args.repository, args.mods, args.backup, args.apply, args.mod or IDS, args.config, args.source_manifest)
