"""Rebuild the published final ROM from Git, a supported original and font sheets."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = '944d2eee3afa7c407624e4c810f48c1ed69e310b5e1c9c58f2aee8091aa97d57'

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-rom', required=True, type=Path)
    p.add_argument('--font-dir', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    config = json.loads((ROOT / 'docs/rebuild/INPUTS.json').read_text(encoding='utf-8'))
    assert a.source_rom.stat().st_size == 8388608 and sha(a.source_rom) == config['source_sha256'], 'Unsupported original'
    for name, digest in config['external_fonts'].items():
        assert sha(a.font_dir / name) == digest, f'Font sheet differs: {name}'
    assert sha(ROOT / 'workspace/assets/title_ko.png') == config['title_sha256'], 'Final title asset differs'
    assert not a.out.exists(), 'Output already exists'
    env = dict(os.environ, MZM_SOURCE_ROM=str(a.source_rom.resolve()), MZM_FONT_DIR=str(a.font_dir.resolve()), PYTHONDONTWRITEBYTECODE='1')
    for name, args in [('extract_text.py', []), ('build.py', ['--release', '--out', str(a.out.resolve())])]:
        subprocess.run([sys.executable, '-X', 'utf8', '-B', str(Path(__file__).with_name(name)), *args], env=env, check=True)
    assert sha(a.out) == EXPECTED, 'Final ROM differs from published release'
    print('PASS: published final ROM reproduced:', EXPECTED)

if __name__ == '__main__':
    main()
