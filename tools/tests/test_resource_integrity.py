import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    'resource_integrity', Path(__file__).resolve().parents[1] / 'audit_resource_integrity.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ResourceIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.repo, self.game = root / 'repo', root / 'game'
        self.data = self.repo / '123/Data'
        (self.data / 'World').mkdir(parents=True)
        (self.game / 'World').mkdir(parents=True)

    def write(self, base, relative, content):
        p = base / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding='utf-8')

    def findings(self):
        return MODULE.audit(self.repo, self.game, ['123'])['findings']

    def test_embedded_language_markup_and_duplicate_keys(self):
        self.write(self.data, 'Core/Languages/English/Weapons.xml',
                   '<language><entry name="Sword" value="<string name=\'Weapons/Melee\'/>"/>'
                   '<entry name="Sword" value="Duplicate"/></language>')
        self.assertEqual(['duplicate_language_key'], [f['code'] for f in self.findings()])

    def test_identifier_case_is_checked_on_windows_too(self):
        self.write(self.data, 'World/Traits/Battlefield.xml', '<trait/>')
        self.write(self.data, 'World/Features/Battlefield.xml',
                   '<feature><traits><trait name="battlefield"/></traits></feature>')
        self.assertEqual('case_mismatch', self.findings()[0]['code'])

    def test_missing_texture_is_reported(self):
        self.write(self.data, 'Video/Materials/Terrain/Ground.xml',
                   '<material><textures><texture name="Terrain/Missing"/></textures></material>')
        self.assertEqual('missing_resource', self.findings()[0]['code'])

    def test_runtime_texture_targets_are_not_files(self):
        material = '<material><textures><texture name="ShadowMapColor"/></textures></material>'
        self.write(self.game, 'Video/Materials/Default.xml', material)
        self.write(self.data, 'Video/Materials/Custom.xml', material)
        self.assertEqual([], self.findings())

    def test_new_units_need_localization_and_both_icons(self):
        self.write(self.data, 'World/Units/Neutral/Custom.xml', '<unit/>')
        findings = self.findings()
        self.assertEqual(3, sum(f['code'] == 'missing_unit_localization' for f in findings))
        self.assertEqual(2, sum(f['code'] == 'missing_resource' for f in findings))

    def test_shipped_references_resolve_without_copying_game_files(self):
        self.write(self.game, 'World/Traits/Flyer.xml', '<trait/>')
        self.write(self.data, 'World/Features/Custom.xml',
                   '<feature><traits><trait name="Flyer"/></traits></feature>')
        self.assertEqual([], self.findings())


if __name__ == '__main__':
    unittest.main()
