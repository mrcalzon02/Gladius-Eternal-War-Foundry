import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    'weapon_attachments', Path(__file__).resolve().parents[1] / 'audit_weapon_attachments.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WeaponAttachmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo, self.game = self.root / 'repo', self.root / 'game'
        self.mod = self.repo / '123/Data'
        (self.game / 'World/Units').mkdir(parents=True)
        self.mesh('Body', ['LeftHandBone', 'RightHandBone'])
        self.mesh('Gun', ['Muzzle0', 'Muzzle1'])

    def mesh(self, name, bones):
        p = self.game / 'Video/Meshes' / (name + '.msh')
        p.parent.mkdir(parents=True, exist_ok=True)
        identity = struct.pack('<16f', 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
        p.write_bytes(b'MSH1.0\0' + bytes([len(bones)]) + b''.join(
            name.encode() + b'\0' + identity for name in bones))
        return p

    def unit(self, attachment='LeftHandBone', muzzle='Muzzle', count=2):
        p = self.mod / 'World/Units/Guard/Custom.xml'
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('<unit><model><unit mesh="Body"/></model><weapons><weapon name="Gun">'
                     '<model><projectileWeapon mesh="Gun" bone="' + attachment + '" muzzleBone="' +
                     muzzle + '" muzzleCount="' + str(count) + '"/></model></weapon></weapons></unit>')

    def report(self):
        return MODULE.audit(self.repo, self.game, ['123'])

    def test_valid_socket_and_numbered_muzzles(self):
        self.unit()
        self.assertEqual([], self.report()['errors'])
        self.assertEqual(1, len(self.report()['reviews']))

    def test_wrong_character_bone(self):
        self.unit(attachment='LeftHand')
        self.assertEqual('missing_attachment_bone', self.report()['errors'][0]['code'])

    def test_missing_numbered_muzzle(self):
        self.unit(count=3)
        self.assertEqual('missing_muzzle_bone', self.report()['errors'][0]['code'])

    def test_mod_mesh_overrides_game_mesh(self):
        self.unit()
        p = self.mod / 'Video/Meshes/Body.xml'
        p.parent.mkdir(parents=True)
        p.write_text('<mesh><bone name="OtherHand"/></mesh>')
        self.assertEqual('missing_attachment_bone', self.report()['errors'][0]['code'])

    def test_invalid_mesh_is_reported(self):
        self.unit()
        (self.game / 'Video/Meshes/Body.msh').write_bytes(b'unsupported')
        self.assertEqual('unreadable_mesh', self.report()['errors'][0]['code'])


if __name__ == '__main__':
    unittest.main()
