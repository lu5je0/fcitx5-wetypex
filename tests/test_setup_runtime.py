import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    'setup_runtime', Path(__file__).resolve().parents[1] / 'scripts/setup_runtime.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class SetupRuntimeTest(unittest.TestCase):
    def test_read_only_package_can_be_installed_and_reinstalled(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source', root / 'user'
            source.mkdir()
            (source / 'theme.conf').write_text('original')
            (source / 'theme.conf').chmod(0o444)
            source.chmod(0o555)
            try:
                setup.copy_user_tree(source, target)
                self.assertTrue(target.stat().st_mode & 0o200)
                self.assertTrue((target / 'theme.conf').stat().st_mode & 0o200)
                # Recover data left behind by the former copytree implementation.
                (target / 'theme.conf').chmod(0o444)
                target.chmod(0o555)
                setup.copy_user_tree(source, target)
                (target / 'next.svg').write_text('new icon')
                self.assertEqual((target / 'theme.conf').read_text(), 'original')
                self.assertEqual(source.stat().st_mode & 0o777, 0o555)
                self.assertEqual((source / 'theme.conf').stat().st_mode & 0o777, 0o444)
            finally:
                source.chmod(0o755)

    def test_destination_symlink_does_not_change_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'package', root / 'user'
            source.mkdir()
            (source / 'theme.conf').write_text('original')
            target.symlink_to(source, target_is_directory=True)
            setup.copy_user_tree(source, target)
            self.assertFalse(target.is_symlink())
            (target / 'theme.conf').write_text('custom')
            self.assertEqual((source / 'theme.conf').read_text(), 'original')

    def test_runtime_fallback_preserves_explicit_override(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            user, packaged = root / 'user', root / 'package'
            bundled = packaged / 'fcitx5-wetypex/runtime'
            bundled.mkdir(parents=True)
            (bundled / 'manifest.txt').touch()
            with patch.dict(os.environ, {'WETYPE_DATA_DIR': str(packaged)}, clear=True):
                self.assertEqual(setup.default_runtime(user), bundled)
                local = user / 'fcitx5-wetypex/runtime'
                local.mkdir(parents=True)
                (local / 'manifest.txt').touch()
                self.assertEqual(setup.default_runtime(user), local)
                os.environ['WETYPE_RUNTIME_DIR'] = str(root / 'explicit')
                self.assertEqual(setup.default_runtime(user), root / 'explicit')

    def test_bundled_setup_is_offline_and_repairs_read_only_themes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            user, packaged = root / 'user', root / 'package'
            for relative in ('fcitx5-wetypex/runtime/manifest.txt',
                             'fcitx5-wetypex/ui/icons/input.svg',
                             'fcitx5/themes/wetypex-light/theme.conf',
                             'fcitx5/themes/wetypex-dark/theme.conf'):
                path = packaged / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('packaged')
            with patch.dict(os.environ, {'XDG_DATA_HOME': str(user),
                                         'WETYPE_DATA_DIR': str(packaged)}, clear=True), \
                 patch('sys.argv', ['setup_runtime.py', '--bundled']), \
                 patch.object(setup.urllib.request, 'urlopen') as download:
                self.assertEqual(setup.main(), 0)
                theme = user / 'fcitx5/themes/wetypex-light'
                (theme / 'theme.conf').chmod(0o444)
                theme.chmod(0o555)
                self.assertEqual(setup.main(), 0)
                download.assert_not_called()
                (theme / 'next.svg').write_text('writable')
                self.assertFalse((user / 'fcitx5-wetypex/runtime').exists())


if __name__ == '__main__':
    unittest.main()
