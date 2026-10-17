import hashlib
import importlib.util
from pathlib import Path
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    'package_runtime', Path(__file__).resolve().parents[1] / 'tools/package_runtime.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class RuntimeAssetTest(unittest.TestCase):
    def prepared(self, root):
        (root / 'NOTICE').write_text('fixture notice')
        sums = []
        for relative in ('share/fcitx5-wetypex/runtime/manifest.txt',
                         'share/fcitx5-wetypex/runtime/flurry/manifest.txt',
                         'share/fcitx5-wetypex/runtime/wxp2p/manifest.txt',
                         'share/fcitx5-wetypex/ui/icons/input.svg'):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(relative.encode())
            sums.append(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {relative}\n')
        (root / 'SHA256SUMS').write_text(''.join(sums))

    def test_archive_is_reproducible_and_contains_only_verified_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepared = root / 'prepared'
            prepared.mkdir()
            self.prepared(prepared)
            first, second = root / 'first.tar.gz', root / 'second.tar.gz'
            digest = package.package_prepared(prepared, first)
            (prepared / 'NOTICE').chmod(0o600)
            self.assertEqual(package.package_prepared(prepared, second), digest)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with tarfile.open(first) as archive:
                self.assertEqual(len(archive.getmembers()), 6)
                self.assertTrue(all(member.isfile() and member.mtime == 0
                                    for member in archive.getmembers()))

    def test_tampered_extra_and_linked_resources_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.prepared(root)
            target = root / 'share/fcitx5-wetypex/runtime/manifest.txt'
            original = target.read_bytes()
            target.write_text('tampered')
            with self.assertRaisesRegex(ValueError, 'Checksum mismatch'):
                package.verify_prepared(root)
            target.write_bytes(original)
            private = root / 'share/fcitx5-wetypex/identity.json'
            private.write_text('private')
            with self.assertRaisesRegex(ValueError, 'do not match'):
                package.verify_prepared(root)
            private.unlink()
            target.unlink()
            target.symlink_to(root / 'NOTICE')
            with self.assertRaisesRegex(ValueError, 'Symlinks'):
                package.verify_prepared(root)


if __name__ == '__main__':
    unittest.main()
