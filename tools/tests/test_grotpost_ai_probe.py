import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

SCRIPT = Path(__file__).resolve().parents[1] / 'build_grotpost_ai_probe.py'
SPEC = importlib.util.spec_from_file_location('grotpost_ai_probe', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def canonical(element):
    element = copy.deepcopy(element)
    for node in element.iter():
        if node.text is not None and not node.text.strip():
            node.text = None
        if node.tail is not None and not node.tail.strip():
            node.tail = None
    return ET.tostring(element)


def fixture():
    return '''<?xml version="1.0" encoding="utf-8"?>
<unit><actions>
<attack/>
<constructImperialStrongpoint name="Orks/ConsGrotpost" cooldown="10">
  <beginTargets><target rangeMax="1"><areas><area affects="Tile"/></areas></target></beginTargets>
</constructImperialStrongpoint>
<constructNoctilithCrown name="FoundryAI/Grotpost" cooldown="10">
 <modifiers><modifier><effects><oreCost base="20"/></effects></modifier></modifiers>
 <beginTargets><target rangeMax="1"><conditions><tile><land/><noUnit/></tile></conditions>
 <areas><area affects="Tile"><modifiers><modifier><effects>
 <addUnit name="Orks/Grotpost"/>
 </effects></modifier></modifiers></area></areas></target></beginTargets>
 <conditions><player><aiControlled/></player><unit><hitpointsFraction greater="0.6"/></unit></conditions>
</constructNoctilithCrown>
</actions></unit>'''


class GrotpostAIProbeTests(unittest.TestCase):
    def test_candidate_keeps_human_cost_radius_and_ai_condition(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'Grotz.xml'
            source.write_text(fixture())
            original = ET.parse(source).getroot()
            before = canonical(original.find("./actions/constructImperialStrongpoint"))
            output = Path(tmp) / 'probe'
            manifest = MODULE.make_probe(source, output)
            built = ET.parse(output / 'Data/World/Units/Orks/Grotz.xml').getroot()
            self.assertEqual(before, canonical(built.find("./actions/constructImperialStrongpoint")))
            self.assertIsNone(built.find('./actions/constructNoctilithCrown'))
            ai = built.find('./actions/deployUnit')
            self.assertEqual(ai.get('unit'), 'Orks/Grotpost')
            self.assertEqual(ai.get('cooldown'), '10')
            self.assertEqual(ai.find('./modifiers/modifier/effects/oreCost').get('base'), '20')
            self.assertIsNotNone(ai.find('./conditions/player/aiControlled'))
            self.assertEqual(ai.find('./beginTargets/target').get('rangeMax'), '1')
            self.assertIsNone(ai.find('.//addUnit'))
            self.assertIsNone(ai.find('./beginTargets/target/areas'))
            self.assertFalse(manifest['mapwide_faction_action_added'])
            self.assertEqual(source.read_text(), fixture())
            with self.assertRaisesRegex(ValueError, 'Refusing to overwrite'):
                MODULE.make_probe(source, output)

    def test_unrecognized_source_is_rejected_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'Grotz.xml'
            source.write_text(fixture().replace('rangeMax="1"', 'rangeMax="-1"'))
            output = Path(tmp) / 'probe'
            with self.assertRaisesRegex(ValueError, 'mapwide'):
                MODULE.make_probe(source, output)
            self.assertFalse(output.exists())

    def test_missing_ai_gate_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'Grotz.xml'
            source.write_text(fixture().replace('<aiControlled/>', '<notAIControlled/>'))
            with self.assertRaisesRegex(ValueError, 'AI-only'):
                MODULE.make_probe(source, Path(tmp) / 'probe')


if __name__ == '__main__':
    unittest.main()
