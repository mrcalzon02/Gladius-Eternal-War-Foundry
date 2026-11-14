import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

SPEC = importlib.util.spec_from_file_location(
    'construction_pilot', Path(__file__).resolve().parents[1] / 'build_ai_construction_pilot.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def action():
    return ET.fromstring('''<constructImperialStrongpoint cooldown="10" requiredUpgrade="Orks/Upgrade">
      <model><action animation="OriginalAnimation"/></model>
      <modifiers><modifier><effects><oreCost base="20"/></effects></modifier></modifiers>
      <beginTargets><target rangeMax="1"><conditions><tile><land/><noUnit/></tile></conditions>
        <areas><area affects="Tile"><modifiers><modifier><effects>
          <addUnit name="Orks/Grotpost"/>
        </effects></modifier></modifiers></area></areas>
      </target></beginTargets></constructImperialStrongpoint>''')


class ConstructionPilotTests(unittest.TestCase):
    def test_original_action_is_not_mutated(self):
        original = action()
        raw = ET.tostring(original)
        MODULE.adapt_action(original, 'Grotpost', 2, 3)
        self.assertEqual(raw, ET.tostring(original))

    def test_costs_builder_range_cooldown_and_research_survive(self):
        original = action()
        human, ai, costs = MODULE.adapt_action(original, 'Grotpost', 2, 3)
        for node in (human, ai):
            self.assertEqual('10', node.get('cooldown'))
            self.assertEqual('Orks/Upgrade', node.get('requiredUpgrade'))
            self.assertEqual('1', node.find('./beginTargets/target').get('rangeMax'))
            self.assertEqual('Orks/Grotpost', node.find('.//addUnit').get('name'))
            self.assertEqual(ET.tostring(original.find('modifiers')), ET.tostring(node.find('modifiers')))
            self.assertEqual(ET.tostring(original.find('model')), ET.tostring(node.find('model')))
        self.assertEqual({'ore':20}, costs)

    def test_human_and_ai_branches_are_separate(self):
        human, ai, _ = MODULE.adapt_action(action(), 'Grotpost', 2, 3)
        self.assertIsNotNone(human.find('./conditions/player/notAIControlled'))
        self.assertIsNone(human.find('./conditions/player/aiControlled'))
        self.assertIsNotNone(ai.find('./conditions/player/aiControlled'))
        self.assertIsNone(ai.find('./conditions/player/notAIControlled'))
        self.assertEqual('constructNoctilithCrown', ai.tag)

    def test_ai_reserves_threat_and_health_guards(self):
        _, ai, _ = MODULE.adapt_action(action(), 'Grotpost', 2, 3)
        self.assertEqual('40', ai.find('./conditions/player/ore').get('greater'))
        self.assertEqual('0.6', ai.find('./conditions/unit/hitpointsFraction').get('greater'))
        enemies = ai.find('./conditions/unit/unitsInRange')
        self.assertEqual({'count':'1','range':'3'}, enemies.attrib)
        self.assertIsNotNone(enemies.find('enemy'))
        self.assertIsNotNone(ai.find('./beginTargets/target/conditions/tile/noEnemyCity'))

    def test_invalid_configuration_is_rejected(self):
        for multiplier in (0, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                MODULE.adapt_action(action(), 'Grotpost', multiplier, 3)

    def test_proactive_outpost_does_not_require_an_enemy(self):
        _, ai, _ = MODULE.adapt_action(action(), 'Grotpost', 2, 3, require_threat=False)
        self.assertIsNone(ai.find('./conditions/unit/unitsInRange'))
        self.assertIsNotNone(ai.find('./conditions/unit/hitpointsFraction'))
        self.assertEqual('1', ai.find('./beginTargets/target').get('rangeMax'))

    def test_build_has_four_adapters_and_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo, output = root/'repo', root/'pilot'
            for mod, unit_name, tag, spawned, _ in MODULE.SPECS:
                p = repo/mod/'Data/World/Units'/(unit_name+'.xml')
                p.parent.mkdir(parents=True, exist_ok=True)
                tree = ET.parse(p) if p.exists() else ET.ElementTree(ET.fromstring('<unit><actions/></unit>'))
                node = action();node.tag = tag;node.find('.//addUnit').set('name', spawned)
                if spawned == 'Orks/Grotpost':
                    node.set('name', 'Orks/ConsGrotpost')
                tree.getroot().find('actions').append(node);tree.write(p)
            manifest = MODULE.build(repo, output)
            self.assertEqual(4, len(manifest['actions']))
            grot = next(a for a in manifest['actions'] if a['spawned_unit'] == 'Orks/Grotpost')
            self.assertFalse(grot['requires_nearby_enemy'])
            self.assertEqual(3, len(list((output/'Data/World/Units').rglob('*.xml'))))
            entries = ET.parse(output/'Data/Core/Languages/English/Actions.xml').getroot()
            self.assertEqual(15, len(entries))
            self.assertIn('Orks/ConsGrotpost', {e.get('name') for e in entries})
            with self.assertRaises(ValueError):
                MODULE.build(repo, output)


if __name__ == '__main__':
    unittest.main()
