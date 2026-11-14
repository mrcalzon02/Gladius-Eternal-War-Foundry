"""Build an optional AI construction test mod from current Foundry unit sources.

No live installation or game configuration is changed. Enable the generated
pilot only with its three required mods and after them in the mod load order.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


SPECS = (
    ('2175959340', 'SpaceMarines/TechpriestEnginseer', 'constructImperialStrongpoint',
     'SpaceMarines/ImperialStrongpoint', 'MarineStrongpoint'),
    ('2525618649', 'AstraMilitarum/TechpriestEnginseer', 'constructImperialStrongpoint',
     'AstraMilitarum/ImperialStrongpoint', 'ImperialStrongpoint'),
    ('2525618649', 'AstraMilitarum/TechpriestEnginseer', 'constructVoidShieldGenerator',
     'AstraMilitarum/VoidShieldGenerator', 'VoidShieldGenerator'),
    ('3038342810', 'Orks/Grotz', 'constructImperialStrongpoint', 'Orks/Grotpost', 'Grotpost'),
)


def add_player_condition(action, condition):
    conditions = action.find('conditions')
    if conditions is None:
        conditions = ET.SubElement(action, 'conditions')
    # A new separate player block is ANDed with any existing action conditions.
    player = ET.SubElement(conditions, 'player')
    ET.SubElement(player, condition)
    return player


def adapt_action(original, action_name, reserve_multiplier, threat_range, require_threat=True):
    if not math.isfinite(reserve_multiplier) or reserve_multiplier < 1 or threat_range < 1:
        raise ValueError('Reserve multiplier and threat range must be at least 1')
    human = copy.deepcopy(original)
    add_player_condition(human, 'notAIControlled')
    human.set('useConditionsForVisiblity', '1')
    ai = copy.deepcopy(original)
    ai.tag = 'constructNoctilithCrown'
    ai.set('name', 'FoundryAI/' + action_name)
    ai.set('useConditionsForVisiblity', '1')
    player = add_player_condition(ai, 'aiControlled')
    ET.SubElement(player, 'noFaction', name='Neutral')
    costs = {}
    for node in original.findall('./modifiers/modifier/effects/*'):
        if node.tag.endswith('Cost') and node.tag != 'productionCost' and 'base' in node.attrib:
            resource = node.tag[:-4]
            costs[resource] = costs.get(resource, 0) + float(node.get('base'))
    for resource, amount in costs.items():
        if amount > 0:
            ET.SubElement(player, resource, greater=f'{amount * reserve_multiplier:g}')
    unit = ET.SubElement(ai.find('conditions'), 'unit')
    ET.SubElement(unit, 'hitpointsFraction', greater='0.6')
    if require_threat:
        enemies = ET.SubElement(unit, 'unitsInRange', count='1', range=str(threat_range))
        ET.SubElement(enemies, 'enemy')
        ET.SubElement(enemies, 'noTrait', name='Invulnerable')
        ET.SubElement(enemies, 'noType', name='Eldar/WebwayGate')
    for tile in ai.findall('./beginTargets/target/conditions/tile'):
        if tile.find('noEnemyCity') is None:
            ET.SubElement(tile, 'noEnemyCity')
    return human, ai, costs


def build(repo, output, reserve_multiplier=2.0, threat_range=3):
    if output.exists():
        raise ValueError(f'Output already exists; choose a new empty destination: {output}')
    if not math.isfinite(reserve_multiplier) or reserve_multiplier < 1 or threat_range < 1:
        raise ValueError('Reserve multiplier and threat range must be at least 1')
    units, inputs, actions, strings = {}, {}, [], {}
    for mod, unit_name, tag, spawned, action_name in SPECS:
        relative = f'{mod}/Data/World/Units/{unit_name}.xml'
        source = repo / relative
        if unit_name not in units:
            raw = source.read_bytes()
            inputs[relative] = hashlib.sha256(raw).hexdigest()
            units[unit_name] = ET.fromstring(raw)
        root = units[unit_name]
        candidates = [node for node in root.findall('./actions/' + tag)
                      if spawned in [effect.get('name') for effect in node.iter('addUnit')]]
        if len(candidates) != 1:
            raise ValueError(f'Expected one construction action: {relative}: {tag}: {spawned}')
        original = candidates[0]
        require_threat = action_name != 'Grotpost'
        human, ai, costs = adapt_action(original, action_name, reserve_multiplier, threat_range, require_threat)
        parent = root.find('actions')
        position = list(parent).index(original)
        parent.remove(original)
        parent.insert(position, human)
        parent.insert(position + 1, ai)
        actions.append(dict(builder=unit_name, spawned_unit=spawned,
                            action=ai.get('name'), cooldown=ai.get('cooldown'),
                            target_ranges=[n.get('rangeMax') for n in ai.findall('./beginTargets/target')],
                            costs=costs, requires_nearby_enemy=require_threat,
                            resource_balance_required_above={k:v*reserve_multiplier for k,v in costs.items()}))
        title = {'MarineStrongpoint': 'Imperial Strongpoint', 'ImperialStrongpoint': 'Imperial Strongpoint',
                 'VoidShieldGenerator': 'Void Shield Generator', 'Grotpost': 'Grotpost'}[action_name]
        strings['FoundryAI/' + action_name] = 'Construct ' + title
        strings['FoundryAI/' + action_name + 'Description'] = 'AI construction test: build ' + title + ' beside this builder.'
        strings['FoundryAI/' + action_name + 'Flavor'] = 'Prepared positions support the army.'
        if original.get('name'):
            # A custom human action needs its own scoped UI strings as well.
            strings[original.get('name')] = 'Construct ' + title
            strings[original.get('name') + 'Description'] = 'Build ' + title + ' beside this builder.'
            strings[original.get('name') + 'Flavor'] = 'Prepared positions support the army.'
    manifest = dict(status='experimental; engine loading and actual AI construction unverified',
                    required_mods=sorted({spec[0] for spec in SPECS}), source_sha256=inputs,
                    reserve_multiplier=reserve_multiplier, threat_range=threat_range,
                    minimum_builder_hitpoints_fraction=0.6, actions=actions,
                    limitations=['Stockpile reserves are not an income or upkeep forecast',
                                 'Enemy proximity is not a battle-strength assessment',
                                 'No mapwide deployment, army movement locks or stat bonuses',
                                 'Duplicate-structure prevention beyond original cooldown is unverified',
                                 'Rebuild from current sources after any dependent unit changes'])
    output.mkdir(parents=True)
    for name, root in units.items():
        path = output / 'Data/World/Units' / (name + '.xml')
        path.parent.mkdir(parents=True, exist_ok=True)
        ET.indent(root, space='\t')
        ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)
    language = ET.Element('language')
    for name, value in strings.items():
        ET.SubElement(language, 'entry', name=name, value=value)
    path = output / 'Data/Core/Languages/English/Actions.xml'
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(language, space='\t')
    ET.ElementTree(language).write(path, encoding='utf-8', xml_declaration=True)
    (output / 'AI_PILOT_MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    (output / 'README.txt').write_text(
        'EXPERIMENTAL FOUNDRY AI CONSTRUCTION PILOT\n'
        'Requires Veteran Marines, Penal Legion, and Proper wagh! enabled.\n'
        'Load this test mod after all three. It overrides three complete unit files.\n'
        'Do not combine with another AI/unit override without comparing the sources.\n'
        'Disable the pilot to restore the original abilities. No SteamID is assigned.\n'
        'Builder, range, original costs, research requirements and cooldowns are retained.\n'
        f'AI must have over 60% health; Guard/Marine defenses require an enemy within {threat_range} tiles.\n'
        'Ork Grotposts do not require a nearby enemy, allowing proactive construction.\n'
        f'and resource balances above {reserve_multiplier:g} times each construction cost.\n'
        'This is a handler experiment, not proven intelligent placement.\n', encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--reserve-multiplier', type=float, default=2)
    parser.add_argument('--threat-range', type=int, default=3)
    args = parser.parse_args()
    try:
        manifest = build(args.repo, args.output, args.reserve_multiplier, args.threat_range)
    except (ValueError, OSError, ET.ParseError) as error:
        parser.error(str(error))
    print(f"Built {len(manifest['actions'])} AI construction adapters in {args.output}")
    print('Not installed or enabled. Gameplay unverified.')


if __name__ == '__main__':
    main()
