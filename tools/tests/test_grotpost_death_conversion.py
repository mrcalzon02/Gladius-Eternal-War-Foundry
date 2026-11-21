"""Static regression tests for the Ork Grotz death-to-Grotpost conversion.

These tests validate XML wiring only. They do NOT assert actual game behavior.
"""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / '3038342810' / 'Data'


class GrotpostDeathConversionTests(unittest.TestCase):
    def read(self, path):
        return ET.parse(DATA / path).getroot()

    def test_only_regular_playable_grotz_carry_new_death_trait(self):
        normal = self.read('World/Units/Orks/Grotz.xml')
        neutral = self.read('World/Units/Neutral/Grotz.xml')
        kamando = self.read('World/Units/Orks/GrotzKamando.xml')
        path = "traits/trait[@name='Orks/GrotpostOnDeath']"
        self.assertEqual(1, len(normal.findall(path)))
        self.assertEqual([], neutral.findall(path))
        self.assertEqual([], kamando.findall(path))
        self.assertIsNotNone(normal.find("traits/trait[@name='Orks/CreateOrkoidFungusOnDeath']"))
        self.assertEqual('1', normal.find('group').get('size'))

    def test_build_button_retained_and_ai_command_removed(self):
        normal = self.read('World/Units/Orks/Grotz.xml')
        human = normal.find("actions/constructImperialStrongpoint[@name='Orks/ConsGrotpost']")
        self.assertIsNotNone(human)
        self.assertEqual('20', human.find('modifiers/modifier/effects/oreCost').get('base'))
        self.assertEqual('1', human.find('beginTargets/target').get('rangeMax'))
        self.assertEqual('Orks/Grotpost', human.find('.//addUnit').get('name'))
        self.assertIsNone(normal.find('actions/constructNoctilithCrown'))

    def test_disappearance_area_spawns_only_one_post_on_current_tile(self):
        trait = self.read('World/Traits/Orks/GrotpostOnDeath.xml')
        self.assertEqual('trait', trait.tag)
        self.assertEqual([], trait.findall('onUnitDisappearedModifiers'))
        areas = trait.findall('onUnitDisappeared/area')
        self.assertEqual(1, len(areas))
        area = areas[0]
        self.assertEqual({'affects': 'Tile', 'radius': '0'}, area.attrib)
        effects = area.findall('modifiers/modifier/effects/*')
        self.assertEqual(1, len(effects))
        self.assertEqual('addUnit', effects[0].tag)
        self.assertEqual('Orks/Grotpost', effects[0].get('name'))

    def test_legal_land_placement_guard(self):
        tile = self.read('World/Traits/Orks/GrotpostOnDeath.xml').find(
            'onUnitDisappeared/area/modifiers/modifier/conditions/tile')
        self.assertIsNotNone(tile)
        for name in ('land', 'noUnit', 'noEnemyCity'):
            self.assertIsNotNone(tile.find(name))
        for name in ('Resource', 'WireWeed'):
            self.assertIsNotNone(tile.find(f"noFeatureCategory[@name='{name}']"))
        self.assertIsNotNone(tile.find("noFeature[@name='GravityWaves']"))

    def test_original_grotpost_stats_and_harvesting_remain(self):
        post = self.read('World/Units/Orks/Grotpost.xml')
        self.assertIsNotNone(post.find("traits/trait[@name='Fortification']"))
        self.assertIsNotNone(post.find("traits/trait[@name='HarvestResourceFeatures']"))
        self.assertIsNotNone(post.find("traits/trait[@name='Transport']"))
        self.assertEqual('32.0', post.find('modifiers/modifier/effects/hitpointsMax').get('base'))

    def test_new_trait_is_localized(self):
        strings = self.read('Core/Languages/English/Traits.xml')
        names = [node.get('name') for node in strings.findall('entry')]
        for suffix in ('', 'Description', 'Flavor'):
            self.assertEqual(1, names.count('Orks/GrotpostOnDeath' + suffix))


if __name__ == '__main__':
    unittest.main()
