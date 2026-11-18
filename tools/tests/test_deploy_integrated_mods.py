import contextlib
import importlib.util
import io
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

SPEC = importlib.util.spec_from_file_location('deploy_integrated_mods', Path(__file__).parents[1] / 'deploy_integrated_mods.py')
DEPLOY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEPLOY)
ITEM = '2525618649'
TITLE = 'Penal Legion'


class LocalDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='deploy-test-', dir=Path(__file__).parents[2])
        self.root = Path(self.temp.name)
        self.repo = self.root / 'source'
        self.mods = self.root / 'Gladius' / 'Mods'
        self.backup = self.root / 'backup'
        self.manifest = self.root / 'source-files.json'
        files = {
            'catalog/mods.json': json.dumps({'mods': [{'workshop_id': ITEM, 'title': TITLE}]}).encode(),
            ITEM + '/SteamID.txt': ITEM.encode(),
            ITEM + '/Preview.png': b'preview',
            ITEM + '/Preview1.png': b'preview1',
            ITEM + '/Tempart.jpg': b'portrait',
            ITEM + '/WORKSHOP.md': b'recovery documentation',
            ITEM + '/Data/World/Units/unit.xml': b'<unit/>',
        }
        for relative, raw in files.items():
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        (self.repo / ITEM / 'Data/untracked-study.xml').write_bytes(b'<rejected/>')
        self.manifest.write_text(json.dumps({'files': list(files)}))
        self.config = self.root / 'Gladius.xml'
        self.workshop = 'C:/Program Files (x86)/Steam/steamapps/workshop/content/489630/' + ITEM
        self.config.write_bytes(b'\xef\xbb\xbf' + ('<?xml version="1.0" encoding="utf-8"?>\r\n<configuration>\r\n'
            '<entry name="Mods/Disabled" value=""/>\r\n'
            '<entry name="Mods/Installed" value="before,' + self.workshop + ',after"/>\r\n'
            '<entry name="Other" value="untouched"/>\r\n</configuration>\r\n').encode())

    def tearDown(self):
        self.temp.cleanup()

    def deploy(self, apply=False):
        with contextlib.redirect_stdout(io.StringIO()), patch.object(DEPLOY, 'ensure_game_closed'):
            return DEPLOY.deploy(self.repo, self.mods, self.backup, apply, [ITEM], self.config, self.manifest)

    def test_dry_run_has_no_side_effects(self):
        before = self.config.read_bytes()
        result = self.deploy()
        self.assertEqual(result['local_folders'], {ITEM: TITLE})
        self.assertTrue(result['config_changes'])
        self.assertFalse(self.backup.exists())
        self.assertFalse(self.mods.exists())
        self.assertEqual(self.config.read_bytes(), before)

    def test_exact_upload_package_and_complete_original_backup(self):
        old = self.mods / TITLE
        old.mkdir(parents=True)
        (old / 'stale.xml').write_bytes(b'old extra file')
        original_config = self.config.read_bytes()
        self.deploy(True)
        self.assertEqual(set(DEPLOY.inventory(old)), {'SteamID.txt', 'Preview.png', 'Preview1.png', 'Tempart.jpg', 'Data/World/Units/unit.xml'})
        self.assertEqual((old / 'SteamID.txt').read_text(), ITEM)
        self.assertEqual((self.backup / 'local-mods' / TITLE / 'stale.xml').read_bytes(), b'old extra file')
        self.assertEqual((self.backup / 'Gladius.xml').read_bytes(), original_config)
        self.assertTrue((self.backup / 'APPLIED.json').is_file())

    def test_config_order_encoding_duplicate_block_and_idempotence(self):
        original = self.config.read_bytes()
        result = DEPLOY.updated_config(original, self.mods, {ITEM: TITLE})
        parsed = {entry.get('name'): entry.get('value') for entry in ET.fromstring(result).findall('entry')}
        self.assertEqual(parsed['Mods/Installed'].split(','), ['before', str(self.mods / TITLE).replace('\\', '/'), 'after'])
        self.assertEqual(parsed['Mods/Disabled'], self.workshop)
        self.assertTrue(result.startswith(b'\xef\xbb\xbf'))
        self.assertEqual(result.count(b'\r\n'), original.count(b'\r\n'))
        self.assertEqual(result, DEPLOY.updated_config(result, self.mods, {ITEM: TITLE}))

    def test_disabled_original_remains_disabled_locally(self):
        original = self.config.read_bytes().replace(b'name="Mods/Disabled" value=""', ('name="Mods/Disabled" value="' + self.workshop + '"').encode())
        result = DEPLOY.updated_config(original, self.mods, {ITEM: TITLE})
        disabled = ET.fromstring(result).find("entry[@name='Mods/Disabled']").get('value').split(',')
        self.assertEqual(disabled, [str(self.mods / TITLE).replace('\\', '/'), self.workshop])
        self.assertEqual(result, DEPLOY.updated_config(result, self.mods, {ITEM: TITLE}))

    def test_failed_install_restores_original_directory_and_config(self):
        target = self.mods / TITLE
        target.mkdir(parents=True)
        (target / 'old.txt').write_bytes(b'original')
        before_config = self.config.read_bytes()
        actual = DEPLOY.bounded_move

        def fail_install(source, destination, source_parent, target_parent):
            if source_parent.name == 'staged':
                raise OSError('simulated installation failure')
            return actual(source, destination, source_parent, target_parent)

        with patch.object(DEPLOY, 'bounded_move', side_effect=fail_install):
            with self.assertRaisesRegex(OSError, 'simulated'):
                self.deploy(True)
        self.assertEqual((target / 'old.txt').read_bytes(), b'original')
        self.assertEqual(self.config.read_bytes(), before_config)
        self.assertFalse((self.backup / 'APPLIED.json').exists())

    def test_steam_destination_and_unsafe_catalog_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'never a Steam'):
            DEPLOY.local_destination(self.root / 'Steam' / 'Mods')
        catalog = self.repo / 'catalog/mods.json'
        catalog.write_text(json.dumps({'mods': [{'workshop_id': ITEM, 'title': '../escape'}]}))
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            self.deploy()

    def test_hashed_manifest_checks_all_files_before_package_selection(self):
        names = json.loads(self.manifest.read_text())['files']
        rows = []
        for name in names:
            raw = (self.repo / name).read_bytes()
            rows.append({'path': name, 'size': len(raw),
                         'git_blob_sha': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()})
        self.manifest.write_text(json.dumps({'files': rows}))
        self.assertEqual(self.deploy()['tracked_package_files'], 5)
        # Recovery documentation is excluded from the upload, but its recorded
        # GitHub blob still has to match the frozen source manifest.
        (self.repo / ITEM / 'WORKSHOP.md').write_bytes(b'changed after export')
        with self.assertRaisesRegex(ValueError, 'Git blob hash mismatch'):
            self.deploy(True)
        self.assertFalse(self.mods.exists())
        self.assertFalse(self.backup.exists())


if __name__ == '__main__':
    unittest.main()
