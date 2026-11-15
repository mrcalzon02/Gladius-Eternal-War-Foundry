"""Check DDS engine compatibility and the construction actions in their parent mods."""
from pathlib import Path
import argparse
import re
import struct
import xml.etree.ElementTree as ET

SPECS = (
    ('2175959340', 'SpaceMarines/TechpriestEnginseer', ('MarineStrongpoint',)),
    ('2525618649', 'AstraMilitarum/TechpriestEnginseer', ('ImperialStrongpoint', 'VoidShieldGenerator')),
    ('3038342810', 'Orks/Grotz', ('Grotpost',)),
)

def validate(root):
    textures = 0
    for mod in root.iterdir():
        if not mod.name.isdigit() or not mod.is_dir():
            continue
        for path in (mod / 'Data').rglob('*.dds'):
            raw = path.read_bytes()
            assert raw[:4] == b'DDS ' and len(raw) >= 128, path
            assert raw[84:88] in (b'DXT1', b'DXT3', b'DXT5'), f'Unsupported DDS format: {path}'
            height, width = struct.unpack_from('<II', raw, 12)
            block = 8 if raw[84:88] == b'DXT1' else 16
            assert len(raw) >= 128 + ((width+3)//4)*((height+3)//4)*block, path
            textures += 1
    for mod, unit, names in SPECS:
        root_unit = ET.parse(root / mod / ('Data/World/Units/' + unit + '.xml')).getroot()
        language = (root / mod / 'Data/Core/Languages/English/Actions.xml').read_text(encoding='utf-8-sig')
        keys = set(re.findall(r'<entry\s+name="([^"]+)"', language))
        actions = root_unit.findall('actions/constructNoctilithCrown')
        found = {a.get('name'): a for a in actions if a.get('name', '').startswith('FoundryAI/')}
        assert set(found) == {'FoundryAI/' + name for name in names}, (mod, found.keys())
        for name, action in found.items():
            native_player = {'aiControlled', 'influence', 'faction', 'noFaction', 'noTrait',
                             'noUpgrade', 'notAIControlled', 'outposts', 'trait', 'upgrade'}
            for player in action.findall('conditions/player'):
                assert {n.tag for n in player} <= native_player, f'Unsupported player condition in {name}'
            assert action.find('conditions/player/aiControlled') is not None, name
            assert action.find("conditions/player/noFaction[@name='Neutral']") is not None, name
            assert action.find('conditions/unit/hitpointsFraction').get('greater') == '0.6', name
            assert action.find('model/action').get('animation', '').startswith('Units/'), name
            for suffix in ('', 'Description', 'Flavor'):
                assert name + suffix in keys, name + suffix
    for mod, unit, model in (
        ('2525618649', 'AstraMilitarum/Guardsman', 'PenalStandardTrooper'),
        ('2525618649', 'AstraMilitarum/Sargent', 'VeteranSergeant'),
        ('2525618649', 'AstraMilitarum/CommissarYarrick', 'Yarrick'),
        ('3038342810', 'Orks/Grotz', 'GrotReplacement'),
        ('2525618729', 'Tyranids/Ripperswarm', 'Ripper'),
    ):
        data = root / mod / 'Data'
        node = ET.parse(data / ('World/Units/' + unit + '.xml')).find('model/unit')
        expected = 'Units/Foundry/' + model
        assert node.get('mesh') == node.get('material') == expected, f'Approved model is not wired into {unit}'
        assert (data / ('Video/Meshes/' + expected + '.msh')).is_file(), unit
        assert (data / ('Video/Materials/' + expected + '.xml')).is_file(), unit
    print(f'Integrated mod validation passed: {textures} engine-compatible DDS files; four AI actions; five approved models wired into their parent mods.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, default=Path(__file__).resolve().parents[1])
    validate(parser.parse_args().repository)
