"""Prepare/apply only the reviewed Yarrick rank correction, with backups."""
from pathlib import Path
from datetime import datetime
import argparse
import hashlib
import json
import shutil
import xml.etree.ElementTree as E

from integrate_yarrick import merge_file
from deploy_integrated_mods import ensure_game_closed

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'assets/yarrick-build'
STAGE = ROOT / 'publication/yarrick-rank-fix'
LIBRARY = Path('C:/GITS/Gladius-Eternal-War-Foundry')
LIVE = Path('C:/Users/Admin/Documents/Proxy Studios/Gladius/Mods/Penal Legion')
RUNTIME = (
    'Data/World/Units/AstraMilitarum/CommissarYarrick.xml',
    'Data/World/Traits/Foundry/ArmageddonCallRank.xml',
    'Data/Core/Languages/English/Actions.xml',
    'Data/Core/Languages/English/Traits.xml',
)
SOURCE = (
    'tools/build_yarrick_rules.py', 'tools/yarrick_call_progression.py',
    'tools/verify_yarrick.py', 'tools/integrate_yarrick.py',
    'tools/deploy_yarrick_rank_fix.py',
    'tools/tests/test_yarrick_call_progression.py', 'docs/YARRICK.txt',
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def prepare():
    records = []
    for category, base, prefix in (('library', LIBRARY, '2525618649/'),
                                   ('installed', LIVE, ''),
                                   ('staged', ROOT/'publication/yarrick', '2525618649/')):
        if category != 'staged':
            assert (base/prefix/'SteamID.txt').read_text().strip() == '2525618649'
        for relative in RUNTIME:
            destination = base / (prefix + relative)
            previous = destination.read_bytes() if destination.exists() else b'<language>\n</language>\n'
            payload = merge_file(relative, (BUILD/relative).read_bytes(), previous)
            target = STAGE / category / (prefix + relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            records.append({'category': category, 'destination': str(destination),
                            'payload': str(target), 'previous_sha256': digest(destination),
                            'sha256': digest(target)})
    for relative in SOURCE:
        target = STAGE/'library'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/relative, target)
        records.append({'category': 'library', 'destination': str(LIBRARY/relative),
                        'payload': str(target), 'previous_sha256': digest(LIBRARY/relative),
                        'sha256': digest(target)})
    manifest = json.loads((BUILD/'MANIFEST.json').read_text())
    manifest['files'] = {p.relative_to(BUILD).as_posix(): digest(p)
                         for p in (BUILD/'Data').rglob('*') if p.is_file()}
    manifest['status'] = 'Single five-rank skill; offline checks passed; live acceptance pending'
    (BUILD/'MANIFEST.json').write_text(json.dumps(manifest, indent=2))
    (STAGE/'plan.json').write_text(json.dumps(records, indent=2))
    print(f'Prepared {len(records)} conflict-checked file updates; four runtime files per copy.')


def apply():
    records = json.loads((STAGE/'plan.json').read_text())
    bases = {'library': LIBRARY, 'installed': LIVE, 'staged': ROOT/'publication/yarrick'}
    for item in records:
        dst, payload = Path(item['destination']), Path(item['payload'])
        assert dst.resolve().is_relative_to(bases[item['category']].resolve()), dst
        assert payload.resolve().is_relative_to(STAGE.resolve()), payload
        assert digest(dst) == item['previous_sha256'], f'Concurrent edit: {dst}'
        assert digest(payload) == item['sha256'], f'Changed payload: {payload}'
    ensure_game_closed()
    backup = ROOT/'backups'/('yarrick-rank-fix-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(parents=True)
    changed = []
    try:
        for item in records:
            dst = Path(item['destination'])
            old = backup/item['category']/dst.relative_to(bases[item['category']])
            if dst.exists():
                old.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, old)
            dst.parent.mkdir(parents=True, exist_ok=True)
            changed.append((dst, old, item['previous_sha256']))
            dst.write_bytes(Path(item['payload']).read_bytes())
            assert digest(dst) == item['sha256'], dst
    except Exception:
        for dst, old, previous in reversed(changed):
            if previous is None:
                dst.unlink(missing_ok=True)
            else:
                shutil.copy2(old, dst)
        raise
    receipt = {'status': 'installed; offline checks passed; in-game acceptance pending',
               'backup': str(backup), 'files': records}
    (STAGE/'DEPLOYMENT.json').write_text(json.dumps(receipt, indent=2))
    print(f'Installed and read back {len(records)} files. Backup: {backup}')


def verify():
    receipt = json.loads((STAGE/'DEPLOYMENT.json').read_text())
    for item in receipt['files']:
        assert digest(Path(item['destination'])) == item['sha256'], item['destination']
    for base in (BUILD, LIBRARY/'2525618649', LIVE, ROOT/'publication/yarrick/2525618649'):
        unit = E.parse(base/RUNTIME[0]).getroot()
        calls = [a for a in unit.findall('actions/*')
                 if (a.get('name') or '').startswith('Foundry/ArmageddonCalls')]
        trained = [a for a in calls if int(a.get('rankMax', '0')) > 0]
        assert len(trained) == 1
        assert trained[0].get('name') == 'Foundry/ArmageddonCalls'
        assert (trained[0].get('rank'), trained[0].get('rankMax')) == ('-1', '4')
        assert not any(a.find('.//conditions/unit/level') is not None for a in calls)
    print('All installed/source hashes match; one untrained five-rank skill in all four copies.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('prepare', 'apply', 'verify'))
    args = parser.parse_args()
    {'prepare': prepare, 'apply': apply, 'verify': verify}[args.operation]()
