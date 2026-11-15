"""Deploy the seven original mod packages and retire superseded local overlays.

Run without --apply to review the plan. Steam Workshop publication is separate.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

IDS = ('2175959340', '2525618649', '2525618729', '3038342810', '3107612342', '3267312159', '3305007655')
RETIRED = ('Foundry AI Construction Pilot', 'Foundry Veteran Sergeant', 'Foundry Grot Replacement', 'Foundry Ripper')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

def deploy(repo, workshop, config, backup, apply=False):
    mods = config.parent.parent / 'Mods'
    old_config = config.read_bytes()
    root = ET.fromstring(old_config)
    entries = {n.get('name'): n for n in root.findall('entry')}
    retired_paths = {str((mods / n).resolve()).replace('\\', '/').rstrip('/').casefold() for n in RETIRED}
    updated = old_config.decode('utf-8-sig')
    for key in ('Mods/Installed', 'Mods/Disabled'):
        if key not in entries:
            continue
        values = [p for p in entries[key].get('value', '').split(',')
                  if p.replace('\\', '/').rstrip('/').casefold() not in retired_paths]
        pattern = r'(<entry\s+name="' + re.escape(key) + r'"\s+value=")[^"]*("\s*/>)'
        updated, count = re.subn(pattern, lambda m: m[1] + ','.join(values) + m[2], updated)
        assert count == 1, key
    ET.fromstring(updated)
    plan = []
    for item in IDS:
        assert (repo / item / 'SteamID.txt').read_text().strip() == item
        assert (workshop / item / 'SteamID.txt').read_text().strip() == item
        for source in sorted((repo / item / 'Data').rglob('*')):
            if not source.is_file():
                continue
            relative = source.relative_to(repo)
            target = workshop / relative
            assert target.resolve().is_relative_to(workshop.resolve())
            if digest(source) != digest(target):
                plan.append(dict(relative=relative.as_posix(), previous_sha256=digest(target), sha256=digest(source)))
    retire = [mods / name for name in RETIRED if (mods / name).is_dir()]
    summary = dict(files=len(plan), retire=[p.name for p in retire], original_mods=list(IDS), config_changes=updated.encode('utf-8') != old_config)
    print(json.dumps(summary, indent=2))
    if not apply:
        return summary
    running = subprocess.check_output(['tasklist', '/FI', 'IMAGENAME eq Gladius.exe', '/FO', 'CSV'], text=True)
    assert '"Gladius.exe"' not in running, 'Close Gladius before deployment'
    assert not backup.exists(), 'Choose a new backup directory'
    backup.mkdir(parents=True)
    (backup / 'Gladius.xml').write_bytes(old_config)
    (backup / 'plan.json').write_text(json.dumps(plan, indent=2))
    # Back up and verify every input before the first installed file changes.
    for item in plan:
        target = workshop / item['relative']
        assert digest(target) == item['previous_sha256']
        assert digest(repo / item['relative']) == item['sha256']
        if target.exists():
            saved = backup / 'workshop' / item['relative']
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
    assert config.read_bytes() == old_config, 'Configuration changed during planning'
    for item in plan:
        target = workshop / item['relative']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / item['relative'], target)
        assert digest(target) == item['sha256'], target
    # Check all package files before removing any override from the active list.
    for item in IDS:
        for source in (repo / item / 'Data').rglob('*'):
            if source.is_file():
                assert digest(source) == digest(workshop / source.relative_to(repo)), source
    for source in retire:
        assert source.resolve().parent == mods.resolve() and source.name in RETIRED
        target = backup / 'retired-overlays' / source.name
        assert target.resolve().is_relative_to(backup.resolve())
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
    config.write_text(updated, encoding='utf-8')
    assert not any((mods / name).exists() for name in RETIRED)
    current = ET.parse(config)
    assert not any(p.replace('\\', '/').rstrip('/').casefold() in retired_paths
                   for entry in current.findall('entry') if entry.get('name') in ('Mods/Installed', 'Mods/Disabled')
                   for p in entry.get('value', '').split(','))
    (backup / 'APPLIED.json').write_text(json.dumps(summary, indent=2))
    print('Integrated parent packages verified; four superseded overlays archived outside the game Mods directory.')
    return summary

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--workshop', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    deploy(args.repository, args.workshop, args.config, args.backup, args.apply)
