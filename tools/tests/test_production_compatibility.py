import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    'audit_production', Path(__file__).resolve().parents[1] / 'audit_production_compatibility.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ProductionCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.repo, self.game = root / 'repo', root / 'game'
        self.mod = self.repo / '123' / 'Data'
        for base in (self.game, self.mod):
            self.write(base, 'World/Units/Guard/Tank.xml', '<unit dlc="Pack"/>')
            self.write(base, 'World/Upgrades/Guard/Tank.xml', '<upgrade dlc="Pack"/>')
        self.action = '<produceUnit unit="Guard/Tank" requiredUpgrade="Guard/Tank"/>'
        for base in (self.game, self.mod):
            self.write(base, 'World/Buildings/Guard/Vehicles.xml',
                       f'<building><actions>{self.action}</actions></building>')

    def write(self, base, relative, value):
        path = base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding='utf-8')

    def codes(self):
        return [item['code'] for item in MODULE.audit(
            self.repo, self.game, ['123'])['findings']]

    def test_game_fallback_and_gladius_language_markup(self):
        (self.mod / 'World/Units/Guard/Tank.xml').unlink()
        (self.mod / 'World/Upgrades/Guard/Tank.xml').unlink()
        self.write(self.mod, 'Core/Languages/English/Units.xml',
                   '<language><entry value="<string name=\'Units/Guard/Tank\'/>"/></language>')
        self.assertEqual([], self.codes())

    def test_missing_production_is_a_regression(self):
        self.write(self.mod, 'World/Buildings/Guard/Vehicles.xml', '<building/>')
        self.assertIn('missing_official_production', self.codes())

    def test_quest_objective_uses_type_attributes(self):
        self.write(self.mod, 'World/Factions/Guard.xml',
                   '<faction><objectives><produceUnit unitType="Guard/Tank"/>'
                   '<constructBuilding buildingType="Guard/Vehicles"/>'
                   '</objectives></faction>')
        self.assertEqual([], self.codes())

    def test_research_gate_cannot_be_removed_silently(self):
        self.write(self.mod, 'World/Buildings/Guard/Vehicles.xml',
                   '<building><actions><produceUnit unit="Guard/Tank"/></actions></building>')
        self.assertIn('changed_official_production', self.codes())

    def test_dlc_gate_cannot_be_removed_silently(self):
        self.write(self.mod, 'World/Units/Guard/Tank.xml', '<unit/>')
        self.assertIn('changed_dlc_gate', self.codes())

    def test_invalid_override_does_not_fall_back_to_game(self):
        self.write(self.mod, 'World/Units/Guard/Tank.xml', '<unit>')
        self.assertIn('invalid_world_xml', self.codes())
        self.assertIn('missing_action_target', self.codes())

    def test_missing_construction_and_research_dependencies(self):
        self.write(self.mod, 'World/Buildings/Guard/Construction.xml',
                   '<building><actions><constructBuilding building="Guard/Absent" '
                   'requiredUpgrade="Guard/Absent"/></actions></building>')
        self.write(self.mod, 'World/Upgrades/Guard/Custom.xml',
                   '<upgrade><requiredUpgrades><upgrade name="Guard/Absent"/>'
                   '</requiredUpgrades></upgrade>')
        self.assertIn('missing_action_target', self.codes())
        self.assertIn('missing_required_upgrade', self.codes())
        self.assertIn('missing_research_prerequisite', self.codes())

    def test_explicit_dependency_resolves_without_hiding_isolated_failure(self):
        self.write(self.mod, 'World/Units/Guard/Tank.xml',
                   '<unit dlc="Pack"><trait requiredUpgrade="Guard/Shared"/></unit>')
        self.write(self.repo / '456/Data', 'World/Upgrades/Guard/Shared.xml', '<upgrade/>')
        self.assertIn('missing_required_upgrade', self.codes())
        report = MODULE.audit(self.repo, self.game, ['123'], ['456'])
        self.assertEqual([], report['findings'])


if __name__ == '__main__':
    unittest.main()
