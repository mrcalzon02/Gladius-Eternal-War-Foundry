"""Read-only production audit against a locally installed Gladius Data directory.

This checks structure, not DLC ownership, engine loading, or AI behavior. Only
World definitions are parsed: Gladius language files use non-standard markup.
"""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def audit(repo, game_data, mod_ids, dependencies=()):
    if not (game_data / 'World/Units').is_dir():
        raise ValueError('--game-data must point to the installed game Data directory')
    findings, summaries, game_inputs = [], [], {}
    for dependency in dependencies:
        if not dependency.isdigit() or not (repo / dependency / 'Data/World').is_dir():
            raise ValueError(f'Invalid dependency mod: {dependency}')

    def official_root(path):
        game_inputs[path.relative_to(game_data).as_posix()] = hashlib.sha256(
            path.read_bytes()).hexdigest()
        return ET.parse(path).getroot()

    def issue(mod, code, path, **details):
        findings.append(dict(mod=mod, code=code, path=path, **details))

    for mod in mod_ids:
        data = repo / mod / 'Data'
        if not (data / 'World').is_dir():
            raise ValueError(f'Mod has no World definitions: {mod}')
        roots, digests = {}, {}
        for path in sorted((data / 'World').rglob('*.xml')):
            relative = path.relative_to(data).as_posix()
            digests[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            try:
                roots[relative] = ET.parse(path).getroot()
            except ET.ParseError as error:
                issue(mod, 'invalid_world_xml', relative, error=str(error))

        def resolve(kind, name):
            relative = f'World/{kind}/{name}.xml'
            if relative in roots:
                return roots[relative]
            # Never silently fall back past an invalid overriding definition.
            if (data / relative).exists():
                return None
            for dependency in reversed(dependencies):
                path = repo / dependency / 'Data' / relative
                if path.is_file():
                    return ET.parse(path).getroot()
            path = game_data / relative
            if path.is_file():
                return official_root(path)
            return None

        production_count = 0
        for relative, root in roots.items():
            for action in root.iter():
                target = None
                if action.tag == 'produceUnit':
                    target = ('Units', action.get('unit') or action.get('unitType'))
                    if action.get('unit'):
                        production_count += 1
                elif action.tag == 'constructBuilding':
                    target = ('Buildings', action.get('building') or action.get('buildingType'))
                if target and (not target[1] or resolve(*target) is None):
                    issue(mod, 'missing_action_target', relative,
                          action=action.tag, target=target[1])
                upgrade = action.get('requiredUpgrade')
                if upgrade and resolve('Upgrades', upgrade) is None:
                    issue(mod, 'missing_required_upgrade', relative, target=upgrade)
                if relative.startswith('World/Upgrades/') and action.tag == 'upgrade':
                    prerequisite = action.get('name')
                    if prerequisite and resolve('Upgrades', prerequisite) is None:
                        issue(mod, 'missing_research_prerequisite', relative,
                              target=prerequisite)

            official_path = game_data / relative
            if not official_path.is_file():
                continue
            official = official_root(official_path)
            if official.get('dlc') and root.get('dlc') != official.get('dlc'):
                issue(mod, 'changed_dlc_gate', relative,
                      expected=official.get('dlc'), actual=root.get('dlc'))
            if not relative.startswith(('World/Buildings/', 'World/Units/')):
                continue
            actual = {}
            for action in root.findall('./actions/produceUnit'):
                actual.setdefault(action.get('unit'), []).append(action.attrib)
            for action in official.findall('./actions/produceUnit'):
                candidates = actual.get(action.get('unit'), [])
                if not candidates:
                    issue(mod, 'missing_official_production', relative,
                          target=action.get('unit'), expected_action=action.attrib)
                elif action.attrib not in candidates:
                    issue(mod, 'changed_official_production', relative,
                          target=action.get('unit'), expected_action=action.attrib,
                          actual_actions=candidates)

        # A custom role needs at least one advertised production route. Do not
        # demand a build-priority effect from a fixed headquarters or every
        # alternate producer (e.g. Ripper Swarms also train at Infantry).
        producers = {}
        for relative, root in roots.items():
            if relative.startswith('World/Buildings/'):
                for action in root.findall('./actions/produceUnit'):
                    producers.setdefault(action.get('unit'), []).append((relative, root))
        for relative, root in roots.items():
            if not relative.startswith('World/Units/') or (game_data / relative).exists():
                continue
            name = relative[len('World/Units/'):-4]
            traits = {node.get('name') for node in root.findall('./traits/trait')}
            role = ('increaseHeroesProductionScore' if 'Hero' in traits else
                    'increaseInfantryProductionScore' if root.find(
                        './strategyModifiers/modifier/effects/increaseInfantryScore') is not None else None)
            routes = producers.get(name, [])
            if role and routes and not all(Path(path).stem == 'Headquarters' for path, _ in routes):
                if not any(node.find('./strategyModifiers/modifier/effects/' + role) is not None
                           for _, node in routes):
                    issue(mod, 'missing_custom_role_strategy', relative, target=name,
                          expected_effect=role, producers=[path for path, _ in routes])

        summaries.append(dict(mod=mod, world_xml=len(digests),
                              production_actions=production_count,
                              input_sha256=digests))
    return dict(scope='source definitions only; no ownership or gameplay attestation',
                dependencies=list(dependencies), game_input_sha256=game_inputs,
                mods=summaries, findings=findings)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--game-data', required=True, type=Path)
    parser.add_argument('--mod', action='append', dest='mods',
                        help='Workshop ID; repeat to select mods; defaults to all numeric folders')
    parser.add_argument('--report', type=Path, help='Optional JSON evidence output')
    parser.add_argument('--dependency', action='append', default=[],
                        help='Explicit fallback mod; repeat in order, last wins; selected mod wins')
    args = parser.parse_args()
    mods = args.mods or sorted(p.name for p in args.repo.iterdir()
                              if p.is_dir() and p.name.isdigit())
    if not mods or any(not mod.isdigit() for mod in mods):
        parser.error('Select at least one numeric Workshop ID')
    try:
        report = audit(args.repo, args.game_data, mods, args.dependency)
    except (ValueError, OSError, ET.ParseError) as error:
        parser.error(str(error))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    for summary in report['mods']:
        print(f"{summary['mod']}: {summary['world_xml']} World XML files, "
              f"{summary['production_actions']} production actions")
    for finding in report['findings']:
        print(f"{finding['mod']} {finding['code']}: {finding['path']} "
              f"{finding.get('target', '')}")
    print(f"{len(report['findings'])} findings. Source checks only; gameplay unverified.")
    return 1 if report['findings'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
