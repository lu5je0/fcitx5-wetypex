#!/usr/bin/env python3
"""Create the reproducible, separately published WeType runtime asset."""
import argparse
import gzip
import hashlib
import importlib.util
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('setup_runtime', ROOT / 'scripts/setup_runtime.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)
ASSET_NAME = f'wetypex-runtime-{setup.UPSTREAM_VERSION}-r1'


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def verify_prepared(directory):
    """Require every shared resource to be listed, regular, and hash-verified."""
    expected = {}
    for line in (directory / 'SHA256SUMS').read_text().splitlines():
        digest, relative = line.split('  ', 1)
        path = PurePosixPath(relative)
        if (len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest)
                or path.is_absolute() or '..' in path.parts or not relative.startswith('share/')
                or relative in expected):
            raise ValueError(f'Invalid checksum entry: {relative}')
        expected[relative] = digest
    actual = set()
    for path in (directory / 'share').rglob('*'):
        if path.is_symlink():
            raise ValueError(f'Symlinks are not allowed: {path}')
        if path.is_file():
            actual.add(path.relative_to(directory).as_posix())
    if not expected or actual != set(expected):
        raise ValueError('Prepared resources do not match SHA256SUMS')
    for relative, digest in expected.items():
        if file_sha256(directory / relative) != digest:
            raise ValueError(f'Checksum mismatch: {relative}')
    for required in ('NOTICE', 'share/fcitx5-wetypex/runtime/manifest.txt',
                     'share/fcitx5-wetypex/runtime/flurry/manifest.txt',
                     'share/fcitx5-wetypex/runtime/wxp2p/manifest.txt',
                     'share/fcitx5-wetypex/ui/icons/input.svg'):
        path = directory / required
        if not path.is_file() or path.is_symlink():
            raise ValueError(f'Missing regular resource: {required}')
    return sorted(['NOTICE', 'SHA256SUMS', *expected])


def package_prepared(directory, output):
    files = verify_prepared(directory)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', mtime=0, filename='') as compressed:
        with tarfile.open(fileobj=compressed, mode='w') as archive:
            for relative in files:
                path = directory / relative
                info = tarfile.TarInfo(f'{ASSET_NAME}/{relative}')
                info.size = path.stat().st_size
                info.mode = 0o644
                with path.open('rb') as source:
                    archive.addfile(info, source)
    return file_sha256(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--archive', type=Path, help='SHA-256-verified official WeType ZIP')
    source.add_argument('--prepared-dir', type=Path, help='existing tree with share/, NOTICE and SHA256SUMS')
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/runtime' / f'{ASSET_NAME}.tar.gz')
    args = parser.parse_args()
    if args.prepared_dir:
        digest = package_prepared(args.prepared_dir.resolve(), args.output)
    else:
        with tempfile.TemporaryDirectory(prefix='wetypex-runtime-') as temporary:
            directory = Path(temporary)
            share = directory / 'share'
            shutil.copytree(ROOT / 'data/themes', share / 'fcitx5/themes')
            environment = dict(os.environ, XDG_DATA_HOME=str(share), WETYPE_DATA_DIR=str(share))
            environment.pop('WETYPE_RUNTIME_DIR', None)
            subprocess.run([sys.executable, str(ROOT / 'scripts/setup_runtime.py'),
                            '--archive', str(args.archive.resolve())], env=environment, check=True)
            shutil.copyfile(ROOT / 'runtime/NOTICE', directory / 'NOTICE')
            sums = []
            for path in sorted(share.rglob('*')):
                if path.is_file():
                    checksum = file_sha256(path)
                    sums.append(f'{checksum}  {path.relative_to(directory).as_posix()}\n')
            (directory / 'SHA256SUMS').write_text(''.join(sums))
            digest = package_prepared(directory, args.output)
    print(args.output)
    print(f'SHA256 {digest}')


if __name__ == '__main__':
    main()
