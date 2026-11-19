"""Regression checks for the generated single-skill reinforcement contract.

This is an XML execution model, not an in-game acceptance test.
"""
import copy
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as E

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from yarrick_call_progression import CALL, PROXY, PENDING


class Model:
    def __init__(self, unit, data, rank, hero_level=0, difficulty=0):
        self.actions = {a.get('name'): a for a in unit.findall('actions/*') if a.get('name')}
        self.proxy = E.parse(data / 'World/Traits/Foundry/ArmageddonCallRank.xml').getroot()
        self.rank = rank
        self.difficulty = difficulty
        self.actor = {'level': hero_level, 'movementMax': 3, 'traits': {}}
        self.target = None
        self.cooldown = 0

    def matches(self, conditions, unit):
        if conditions is None:
            return True
        for n in conditions.findall('unit/*'):
            if n.tag == 'trait' and n.get('name') not in unit['traits']:
                return False
            if n.tag == 'noTrait' and n.get('name') in unit['traits']:
                return False
            if n.tag in ('movementMax', 'level'):
                value = unit[n.tag]
                if n.tag == 'movementMax' and PROXY in unit['traits']:
                    effect = self.proxy.find('.//movementMax')
                    strength = unit['traits'][PROXY] / int(self.proxy.get('rankMax'))
                    low = float(effect.get('minMin')) * (1-strength) + float(effect.get('minMax')) * strength
                    high = float(effect.get('maxMin')) * (1-strength) + float(effect.get('maxMax')) * strength
                    value = min(high, max(low, value))
                if 'greater' in n.attrib and value <= float(n.get('greater')):
                    return False
                if 'less' in n.attrib and value >= float(n.get('less')):
                    return False
        return True

    def available(self):
        return [name for name, a in self.actions.items()
                if name.startswith(CALL) and self.matches(a.find('conditions'), self.actor)
                and (name != CALL or self.rank >= 0)]

    def cast(self, name=CALL, blocked=False):
        a = self.actions[name]
        if blocked or not self.matches(a.find('conditions'), self.actor):
            return False
        if name == CALL and (self.rank < 0 or self.cooldown):
            return False
        assert len(a.findall('beginTargets')) == 1
        source_rank = self.rank if name == CALL else 0
        for target in a.find('beginTargets'):
            for ar in target.findall('areas/area'):
                unit = self.actor if target.tag == 'selfTarget' else self.target
                for modifier in ar.findall('modifiers/modifier'):
                    if modifier.find('conditions') is not None and not self.matches(modifier.find('conditions'), unit):
                        continue
                    for effect in modifier.find('effects'):
                        if effect.tag == 'addUnit':
                            assert effect.get('levelMin') == effect.get('levelMax')
                            self.target = {'type': effect.get('name'),
                                           'level': int(effect.get('levelMin')) + self.difficulty,
                                           'movementMax': 3, 'traits': {}}
                        elif effect.tag == 'addTrait':
                            unit['traits'][effect.get('name')] = source_rank
                        elif effect.tag == 'removeTrait':
                            unit['traits'].pop(effect.get('name'), None)
                        elif effect.tag == 'level':
                            unit['level'] += float(effect.get('add', '0'))
                        else:
                            raise AssertionError(effect.tag)
        self.cooldown = int(a.get('cooldown')) if name == CALL else self.cooldown
        return True


class ProgressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = ROOT / 'assets/yarrick-build/Data'
        cls.unit = E.parse(cls.data / 'World/Units/AstraMilitarum/CommissarYarrick.xml').getroot()

    def model(self, rank, **kw):
        return Model(self.unit, self.data, rank, **kw)

    def test_one_purchased_skill_and_no_hero_level_routing(self):
        calls = [a for a in self.unit.findall('actions/*') if (a.get('name') or '').startswith(CALL)]
        trained = [a for a in calls if int(a.get('rankMax', '0')) > 0]
        self.assertEqual([a.get('name') for a in trained], [CALL])
        self.assertEqual((trained[0].get('rank'), trained[0].get('rankMax')), ('-1', '4'))
        self.assertFalse(any(a.find('.//conditions/unit/level') is not None for a in calls))
        self.assertTrue(all(len(a.findall('beginTargets')) == 1 for a in calls))

    def test_untrained_even_on_maximum_level_hero(self):
        model = self.model(-1, hero_level=9)
        self.assertEqual(model.available(), [])
        self.assertFalse(model.cast())

    def test_exact_five_ranks_independent_of_hero_level_and_difficulty(self):
        expected = [(0, None), (0, 0), (1, 1), (2, 2), (3, 3)]
        for rank, (infantry, tank) in enumerate(expected):
            for hero_level in range(10):
                for difficulty in (0, 2):
                    with self.subTest(rank=rank, hero=hero_level, difficulty=difficulty):
                        model = self.model(rank, hero_level=hero_level, difficulty=difficulty)
                        self.assertEqual(model.available(), [CALL])
                        self.assertTrue(model.cast())
                        self.assertEqual(model.target['level'], infantry + difficulty)
                        self.assertNotIn(PROXY, model.target['traits'])
                        self.assertNotIn(PROXY, model.actor['traits'])
                        self.assertEqual(model.actor['level'], hero_level)
                        self.assertEqual(model.actor['movementMax'], 3)
                        if tank is None:
                            self.assertNotIn(PENDING, model.actor['traits'])
                        else:
                            pending = model.available()
                            self.assertEqual(len(pending), 1)
                            self.assertNotEqual(pending[0], CALL)
                            self.assertTrue(model.cast(pending[0]))
                            self.assertEqual(model.target['type'], 'AstraMilitarum/LemanRussBattleTank')
                            self.assertEqual(model.target['level'], tank + difficulty)
                            self.assertEqual(model.available(), [CALL])
                            self.assertEqual(model.actor['traits'], {})
                        self.assertEqual(model.cooldown, 10)
                        self.assertFalse(model.cast())

    def test_upgrade_and_serialized_pending_reservation(self):
        model = self.model(1)
        model.cast()
        model.rank = 4
        model.actor = json.loads(json.dumps(model.actor))
        self.assertFalse(model.cast())
        model.cast(model.available()[0])
        self.assertEqual(model.target['level'], 0)
        self.assertFalse(model.cast())
        model.cooldown = 0
        model.cast()
        self.assertEqual(model.target['level'], 3)

    def test_blocked_tiles_preserve_call_and_reservation(self):
        model = self.model(3)
        before = copy.deepcopy(model.actor)
        self.assertFalse(model.cast(blocked=True))
        self.assertEqual(model.actor, before)
        self.assertEqual(model.cooldown, 0)
        model.cast()
        before = copy.deepcopy(model.actor)
        self.assertFalse(model.cast(model.available()[0], blocked=True))
        self.assertEqual(model.actor, before)
        self.assertEqual(model.cooldown, 10)


if __name__ == '__main__':
    unittest.main()
