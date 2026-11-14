"""Read-only, case-sensitive entity, texture and localization checks for Gladius.

The language scanner accepts Gladius's embedded string markup. It does not run
the engine or prove gameplay, AI behavior, or complete localization coverage.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def language_keys(text):
    return re.findall(r'<entry\s+name="([^"]+)"', text)


def audit(repo, game, mods):
    official = {p.relative_to(game).as_posix() for p in game.rglob('*') if p.is_file()}
    # Shipped materials also reference runtime render targets, not texture files.
    runtime_textures = set()
    for path in (game / 'Video/Materials').rglob('*.xml'):
        for node in ET.parse(path).getroot().iter('texture'):
            name = node.get('name')
            if name and '/' not in name and f'Video/Textures/{name}.dds' not in official:
                runtime_textures.add(name)
    official_languages = {}
    for path in (game / 'Core/Languages/English').glob('*.xml'):
        official_languages[path.stem] = set(language_keys(path.read_text(encoding='utf-8-sig')))
    findings, count = [], 0
    for mod in mods:
        data = repo / mod / 'Data'
        if not (data / 'World').is_dir():
            raise ValueError(f'Mod has no World data: {mod}')
        own = {p.relative_to(data).as_posix() for p in data.rglob('*') if p.is_file()}
        available = own | official
        folded = {name.casefold(): name for name in sorted(available)}
        languages = {}

        def issue(code, source, **details):
            findings.append(dict(mod=mod, code=code, path=source, **details))

        def reference(relative, source):
            if relative in available:
                return
            actual = folded.get(relative.casefold())
            issue('case_mismatch' if actual else 'missing_resource', source,
                  target=relative, actual=actual)

        for path in sorted((data / 'Core/Languages/English').glob('*.xml')):
            keys = language_keys(path.read_text(encoding='utf-8-sig'))
            languages[path.stem] = set(keys)
            for key, n in Counter(keys).items():
                if n > 1:
                    issue('duplicate_language_key', path.relative_to(data).as_posix(), target=key)

        for path in sorted((data / 'World').rglob('*.xml')):
            root = ET.parse(path).getroot()
            relative = path.relative_to(data).as_posix()
            count += 1
            for node in root.iter():
                if node.tag in ('trait', 'noTrait') and node.get('name'):
                    reference(f"World/Traits/{node.get('name')}.xml", relative)
                if node.tag in ('addFeature', 'removeFeature') and node.get('name'):
                    reference(f"World/Features/{node.get('name')}.xml", relative)
            for node in root.findall('./weapons/weapon'):
                if node.get('name'):
                    reference(f"World/Weapons/{node.get('name')}.xml", relative)
            if relative.startswith('World/Units/'):
                entity = relative[len('World/Units/'):-4]
                # Validate both implicit icon paths only for genuinely new units.
                if relative not in official:
                    icon = root.get('icon') or 'Units/' + entity
                    reference(f'Video/Textures/Icons/{icon}.dds', relative)
                    if icon.startswith('Units/'):
                        reference(f'Video/Textures/Icons/Overlay/{icon}.dds', relative)
                    keys = languages.get('Units', set()) | official_languages.get('Units', set())
                    for suffix in ('', 'Description', 'Flavor'):
                        if entity + suffix not in keys:
                            issue('missing_unit_localization', relative, target=entity + suffix)

        for path in sorted((data / 'Video/Materials').rglob('*.xml')):
            for node in ET.parse(path).getroot().iter('texture'):
                name = node.get('name')
                if name and name not in runtime_textures:
                    reference(f'Video/Textures/{name}.dds', path.relative_to(data).as_posix())
    return dict(scope='Isolated mods: trait/feature/weapon references, material textures, '
                'new-unit English names and icons; gameplay and AI unverified',
                world_xml_checked=count, findings=findings)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--game-data', required=True, type=Path)
    parser.add_argument('--mod', action='append')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    mods = args.mod or sorted(p.name for p in args.repo.iterdir() if p.is_dir() and p.name.isdigit())
    if not (args.game_data / 'World').is_dir() or not mods or any(not m.isdigit() for m in mods):
        parser.error('Provide installed game Data and numeric mod IDs')
    try:
        report = audit(args.repo, args.game_data, mods)
    except (ValueError, OSError, ET.ParseError) as error:
        parser.error(str(error))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f"{report['world_xml_checked']} World XML files; {len(report['findings'])} findings")
    for finding in report['findings']:
        print(json.dumps(finding))
    return 1 if report['findings'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
