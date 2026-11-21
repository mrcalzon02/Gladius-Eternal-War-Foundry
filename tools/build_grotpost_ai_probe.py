"""Create an opt-in Grotz-local deployUnit AI probe from Proper wagh! sources.

This deliberately does not edit installed mods, the main mod, or any save.
The game's AI recognition of deployUnit on *unit* actions is NOT established.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

SOURCE = Path('3038342810/Data/World/Units/Orks/Grotz.xml')
SPAWNED = 'Orks/Grotpost'


def make_probe(source: Path, output: Path) -> dict:
    """Emit a single-unit override as a disposable test mod; never overwrite."""
    if output.exists():
        raise ValueError(f'Refusing to overwrite existing probe: {output}')
    original = source.read_bytes()
    root = ET.fromstring(original)
    actions = root.find('actions')
    if actions is None:
        raise ValueError('Source Grotz unit is missing actions')
    human = [a for a in actions if a.tag == 'constructImperialStrongpoint'
             and a.get('name') == 'Orks/ConsGrotpost']
    ai = [a for a in actions if a.tag == 'constructNoctilithCrown'
          and a.get('name') == 'FoundryAI/Grotpost']
    if len(human) != 1 or len(ai) != 1:
        raise ValueError('Expected one intact Grotz human action and one AI action')
    human_bytes = ET.tostring(human[0])
    candidate = copy.deepcopy(ai[0])
    spawned = candidate.findall('.//addUnit')
    targets = candidate.findall('./beginTargets/target')
    if len(spawned) != 1 or spawned[0].get('name') != SPAWNED or len(targets) != 1:
        raise ValueError('Grotpost AI spawn or target pattern has changed; re-audit')
    if targets[0].get('rangeMax') != '1':
        raise ValueError('Will not generate a mapwide/local-radius-changing probe')
    if candidate.find('./modifiers/modifier/effects/oreCost') is None:
        raise ValueError('Grotpost ore cost is missing')
    if any(effect.tag != 'addUnit' for effect in candidate.findall('.//effects/*')
           if effect.tag != 'oreCost'):
        raise ValueError('Unexpected Grotpost AI effect; re-audit before replacing')
    if candidate.find('./conditions/player/aiControlled') is None:
        raise ValueError('AI-only condition is missing')
    candidate.tag = 'deployUnit'
    candidate.set('unit', SPAWNED)
    # Native deployment carries out the spawn. Retaining addUnit would risk
    # creating duplicates if the action type loads, so remove the old area.
    for target in targets:
        area = target.find('areas')
        if area is not None:
            target.remove(area)
    location = list(actions).index(ai[0])
    actions.remove(ai[0])
    actions.insert(location, candidate)
    if ET.tostring(human[0]) != human_bytes:
        raise AssertionError('Human construction action was modified')
    if root.find('./actions/deployUnit') is None:
        raise AssertionError('Candidate was not inserted')

    destination = output / 'Data/World/Units/Orks/Grotz.xml'
    destination.parent.mkdir(parents=True)
    ET.indent(root, space='\t')
    ET.ElementTree(root).write(destination, encoding='utf-8', xml_declaration=True)
    manifest = {
        'status': 'EXPERIMENTAL: static generation only; game load and AI use unverified',
        'source': SOURCE.as_posix(),
        'source_sha256': hashlib.sha256(original).hexdigest(),
        'variant': 'unit-local deployUnit handler probe',
        'actor': 'Orks/Grotz',
        'spawned_unit': SPAWNED,
        'target_range_max': 1,
        'human_action_unchanged': True,
        'ai_action_tag_before': 'constructNoctilithCrown',
        'ai_action_tag_after': 'deployUnit',
        'mapwide_faction_action_added': False,
        'native_unit_deploy_ai_support_unverified': True,
    }
    (output / 'PROBE.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    (output / 'README.txt').write_text(
        'GROTPOST AI ACTION-TYPE PROBE -- EXPERIMENTAL, NOT A RELEASE\n'
        'Requires Proper wagh! (3038342810) enabled and loaded BEFORE this probe.\n'
        'Use a new skirmish and a disposable test configuration; do not load old saves.\n'
        'This replaces only the Orks/Grotz unit XML and preserves its human build action.\n'
        'AI branch changes from constructNoctilithCrown to deployUnit unit=Orks/Grotpost.\n'
        'The AI unit-action dispatch path is unverified and may reject this XML.\n'
        'DO NOT publish to Workshop or call it fixed before headed game verification.\n'
        'Disable/delete this probe to revert. It contains no SteamID.txt.\n',
        encoding='utf-8',
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True,
                        help='New, non-existing directory; existing paths are never overwritten')
    args = parser.parse_args()
    try:
        result = make_probe(args.repo / SOURCE, args.output)
    except (OSError, ValueError, ET.ParseError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))
    print('Written only to requested output. NOT installed, NOT runtime-tested.')


if __name__ == '__main__':
    main()
