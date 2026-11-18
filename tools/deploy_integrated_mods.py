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
RETIRED_PARENTS = {
    'Foundry AI Construction Pilot': {'2175959340', '2525618649', '3038342810'},
    'Foundry Veteran Sergeant': {'2525618649'},
    'Foundry Grot Replacement': {'3038342810'},
    'Foundry Ripper': {'2525618729'},
}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

def deploy(repo, workshop, config, backup, apply=False, mod_ids=IDS):
    repo, workshop, config, backup = (p.resolve() for p in (repo, workshop, config, backup))
    selected = tuple(dict.fromkeys(mod_ids))
    assert selected and set(selected) <= set(IDS), 'Select existing parent mod IDs'
    eligible_retired = tuple(name for name in RETIRED if RETIRED_PARENTS[name] <= set(selected))
    # A checkout can contain rejected local studies. Only tracked runtime files
    # belong to the current mod; never deploy arbitrary untracked Data files.
    tracked = subprocess.check_output(
        ['git', '-C', str(repo), 'ls-files', '-z', '--', *[item + '/Data' for item in selected]],
    ).decode('utf-8').split('\0')
    sources = [repo / relative for relative in tracked if relative]
    assert sources and all(p.is_file() and p.resolve().is_relative_to(repo) for p in sources)
    mods = config.parent.parent / 'Mods'
    old_config = config.read_bytes()
    root = ET.fromstring(old_config)
    entries = {n.get('name'): n for n in root.findall('entry')}
    retired_paths = {str((mods / n).resolve()).replace('\\', '/').rstrip('/').casefold() for n in eligible_retired}
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
    for item in selected:
        assert (repo / item / 'SteamID.txt').read_text().strip() == item
        assert (workshop / item / 'SteamID.txt').read_text().strip() == item
        for source in sorted(p for p in sources if p.relative_to(repo).parts[0] == item):
            relative = source.relative_to(repo)
            target = workshop / relative
            assert target.resolve().is_relative_to(workshop.resolve())
            if digest(source) != digest(target):
                plan.append(dict(relative=relative.as_posix(), previous_sha256=digest(target), sha256=digest(source)))
    new_config = (b'\xef\xbb\xbf' if old_config.startswith(b'\xef\xbb\xbf') else b'') + updated.encode('utf-8')
    retire = [mods / name for name in eligible_retired if (mods / name).is_dir()]
    summary = dict(files=len(plan), tracked_runtime_files=len(sources), retire=[p.name for p in retire], original_mods=list(selected), config_changes=new_config != old_config)
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
    for source in sources:
        assert digest(source) == digest(workshop / source.relative_to(repo)), source
    for source in retire:
        assert source.resolve().parent == mods.resolve() and source.name in RETIRED
        target = backup / 'retired-overlays' / source.name
        assert target.resolve().is_relative_to(backup.resolve())
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
    if new_config != old_config:
        config.write_bytes(new_config)
    assert config.read_bytes() == new_config
    assert not any((mods / name).exists() for name in eligible_retired)
    current = ET.parse(config)
    assert not any(p.replace('\\', '/').rstrip('/').casefold() in retired_paths
                   for entry in current.findall('entry') if entry.get('name') in ('Mods/Installed', 'Mods/Disabled')
                   for p in entry.get('value', '').split(','))
    (backup / 'APPLIED.json').write_text(json.dumps(summary, indent=2))
    print('Selected parent packages verified; eligible superseded overlays archived outside the game Mods directory.')
    return summary

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--workshop', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--mod', action='append', choices=IDS, help='Deploy only this parent mod; repeat to select several. Defaults to all seven.')
    args = parser.parse_args()
    deploy(args.repository, args.workshop, args.config, args.backup, args.apply, args.mod or IDS)
