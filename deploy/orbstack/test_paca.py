"""Backup destination safeguards: python3 -m unittest -v test_paca.py."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import paca


class CredentialUpgradeTests(unittest.TestCase):
    def test_upgrade_preserves_credentials_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            env = Path(temp) / '.env'
            original = 'JWT_SECRET=existing\nPOSTGRES_PASSWORD=unchanged'
            env.write_text(original)
            paca.ensure_env_secret(env, 'VALKEY_PASSWORD')
            upgraded = env.read_text()
            self.assertTrue(upgraded.startswith(original + '\n'))
            self.assertRegex(upgraded, r'VALKEY_PASSWORD=[0-9a-f]{64}\n$')
            self.assertEqual(env.stat().st_mode & 0o777, 0o600)
            paca.ensure_env_secret(env, 'VALKEY_PASSWORD')
            self.assertEqual(env.read_text(), upgraded)

    def test_upgrade_preserves_an_existing_valkey_password(self):
        with tempfile.TemporaryDirectory() as temp:
            env = Path(temp) / '.env'
            original = 'VALKEY_PASSWORD=already-configured\nJWT_SECRET=existing\n'
            env.write_text(original)
            paca.ensure_env_secret(env, 'VALKEY_PASSWORD')
            self.assertEqual(env.read_text(), original)

    def test_failed_atomic_replacement_leaves_credentials_intact(self):
        with tempfile.TemporaryDirectory() as temp:
            env = Path(temp) / '.env'
            original = 'JWT_SECRET=existing\nVALKEY_PASSWORD=GENERATE\n'
            env.write_text(original)
            with patch.object(paca.os, 'replace', side_effect=OSError('unavailable')):
                with self.assertRaises(OSError):
                    paca.ensure_env_secret(env, 'VALKEY_PASSWORD')
            self.assertEqual(env.read_text(), original)
            self.assertEqual(list(Path(temp).glob('.env-upgrade-*')), [])


class BackupTargetTests(unittest.TestCase):
    def test_missing_network_mount_is_rejected(self):
        fake = subprocess.CompletedProcess([], 0, '/dev/disk3s5 on / (apfs, local)\n', '')
        with patch.object(paca, 'run', return_value=fake):
            with self.assertRaisesRegex(RuntimeError, 'not mounted'):
                paca.mount_for(Path('/Volumes/Personal/Backups'))

    def test_nested_path_selects_smb_mount(self):
        fake = subprocess.CompletedProcess([], 0, '/dev/disk3s5 on / (apfs, local)\n//user@nas/Personal on /Volumes/Personal (smbfs, nodev)\n', '')
        with patch.object(paca, 'run', return_value=fake):
            self.assertEqual(paca.mount_for(Path('/Volumes/Personal/Backups'))['type'], 'smbfs')

    def test_copy_is_verified_and_rerun_preserves_existing_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, target = root / 'local', root / 'nas'
            source.mkdir(); target.mkdir()
            (source / 'paca-test.tar.age').write_bytes(b'fake encrypted content')
            with patch.object(paca, 'BACKUPS', source), patch.object(paca, 'nas_target', return_value=target):
                paca.upload_pending()
                paca.upload_pending()
                self.assertEqual((target / 'paca-test.tar.age').read_bytes(), b'fake encrypted content')
                self.assertTrue((target / 'paca-test.tar.age.sha256').exists())
                self.assertFalse(list(target.glob('*.partial')))
                (target / 'paca-test.tar.age').write_bytes(b'corruption')
                with self.assertRaisesRegex(RuntimeError, 'different checksum'):
                    paca.upload_pending()

    def test_mount_identity_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'backup-target.json').write_text(json.dumps({'mount': {'source': 'expected'}, 'destination': temp, 'instance': 'id'}))
            with patch.object(paca, 'KEYS', root), patch.object(paca, 'mount_for', return_value={'source': 'different'}):
                with self.assertRaisesRegex(RuntimeError, 'differs'):
                    paca.nas_target()

    def test_unavailable_nas_keeps_local_queue(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / 'paca-test.tar.age'
            archive.write_bytes(b'encrypted queued copy')
            with patch.object(paca, 'BACKUPS', root), patch.object(paca, 'nas_target', side_effect=RuntimeError('not mounted')):
                with self.assertRaisesRegex(RuntimeError, 'not mounted'):
                    paca.upload_pending()
                self.assertTrue(archive.exists())

    def test_stopped_application_is_not_started_by_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(paca, 'BASE', Path(temp)), patch.object(paca, 'states', return_value={}), \
                 patch.object(paca, 'upload_pending', return_value='verified target'), patch.object(paca, 'dc') as docker:
                paca.backup()
                docker.assert_not_called()
                self.assertIn('skipped', json.loads((Path(temp) / 'backup-status.json').read_text())['result'])


class ApiImageTests(unittest.TestCase):
    def test_compose_runs_the_locally_built_api_and_never_pulls_it(self):
        compose = (Path(paca.SOURCE) / 'compose.yaml').read_text()
        api = compose.split('\n  api:\n', 1)[1].split('\n  web:\n', 1)[0]
        self.assertIn('image: ' + paca.API_IMAGE + '\n', api)
        self.assertIn('pull_policy: never', api)
        lock = json.loads((Path(paca.SOURCE) / 'images.lock.json').read_text())
        self.assertEqual(lock['api_build']['image'], paca.API_IMAGE)
        self.assertEqual(lock['api_build']['version'], paca.API_VERSION)

    def test_build_uses_this_checkouts_api_source(self):
        with patch.object(paca, 'run') as run:
            paca.build_api()
        args = [str(a) for a in run.call_args.args[0]]
        self.assertEqual(args[-1], str(Path(paca.SOURCE).parent.parent / 'services' / 'api'))
        self.assertIn(paca.API_IMAGE, args)

    def test_build_refuses_without_the_source_tree(self):
        with patch.object(paca, 'SOURCE', paca.BASE), self.assertRaises(RuntimeError):
            paca.build_api()


if __name__ == '__main__':
    unittest.main()
