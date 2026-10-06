#!/usr/bin/env python3
"""Build only when invoked deliberately after user approval."""
import argparse
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from saveconfig import VERSION

PUBLIC = ['tools_cleanup.py', 'saveconfig.py', 'saveconfig', 'resources', 'lang', 'help', 'LICENSE', 'README.md', 'CHANGELOG.md']
SOURCE = PUBLIC + ['start.sh', 'erstelledeb.sh', 'erstellegithub.sh', 'tools', 'packaging', 'tests', '.gitignore', 'github', '.github']


def paths(names):
    for name in names:
        base = ROOT / name
        if not base.exists():
            raise ValueError('Missing required source: ' + name)
        candidates = [base] if base.is_file() else list(base.rglob('*'))
        for path in candidates:
            if path.is_symlink():
                raise ValueError('Symbolic link in source: ' + str(path.relative_to(ROOT)))
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                yield path


def security(files):
    forbidden = {'.env', '.venv', 'settings.json', 'id_rsa', 'id_ed25519'}
    for path in files:
        if any(part in forbidden for part in path.relative_to(ROOT).parts):
            raise ValueError('Private file: ' + str(path.relative_to(ROOT)))
        if path.suffix in ('.png', '.jpg'):
            continue
        content = path.read_text(encoding='utf-8')
        # Check obvious patterns only. Never echo matched values.
        checks = [r'-----BEGIN [A-Z ]*PRIVATE KEY-----', r'gh[pousr]_[A-Za-z0-9]{20,}', r'github_pat_[A-Za-z0-9_]{20,}', r'(?i)(password|token|secret)\s*=\s*[\x22\x27][^\x22\x27]{8,}']
        if any(re.search(pattern, content) for pattern in checks):
            raise ValueError('Suspicious contents: ' + str(path.relative_to(ROOT)))


def copy(files, target):
    for path in files:
        out = target / path.relative_to(ROOT)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, out)
        out.chmod(0o755 if path.name.endswith('.sh') else 0o644)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['source', 'deb'])
    args = parser.parse_args()
    if not re.fullmatch(r'\d+\.\d+\.\d+', VERSION):
        raise ValueError('Invalid central version')
    if (ROOT / '.env').exists():
        raise ValueError('Forbidden .env in source root')
    files = list(paths(SOURCE if args.mode == 'source' else PUBLIC))
    security(files)
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    if args.mode == 'source':
        target = output / ('saveconfig-source-' + VERSION)
        if target.exists():
            import datetime
            target = target.with_name(target.name + '-' + datetime.datetime.now().strftime('%Y%m%d%H%M%S%f'))
        target.mkdir()  # Existing source snapshots are never overwritten.
        copy(files, target)
        print('Quellstand vorbereitet:', target, 'Dateien:', len(files), 'Version:', VERSION)
        return
    target = output / ('saveconfig_' + VERSION + '_all.deb')
    if target.exists():
        raise ValueError('Package already exists; preserve it before rebuilding')
    work = ROOT / 'work'
    work.mkdir(exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='deb-', dir=work))
    app = stage / 'usr/share/saveconfig'
    copy(files, app)
    # Help source is for development; users receive generated offline HTML.
    for path in app.glob('help/*/*.dm'):
        path.unlink()
    executable = stage / 'usr/bin/saveconfig'
    executable.parent.mkdir(parents=True)
    executable.write_text('#!/bin/sh\nexec /usr/bin/python3 -B /usr/share/saveconfig/saveconfig.py "$@"\n')
    executable.chmod(0o755)
    desktop = stage / 'usr/share/applications/saveconfig.desktop'
    desktop.parent.mkdir(parents=True)
    shutil.copy2(ROOT / 'packaging/saveconfig.desktop', desktop)
    doc = stage / 'usr/share/doc/saveconfig'
    doc.mkdir(parents=True)
    shutil.copy2(ROOT / 'LICENSE', doc / 'copyright')
    shutil.copy2(ROOT / 'README.md', doc / 'README.md')
    control = stage / 'DEBIAN'
    control.mkdir()
    (control / 'control').write_text(f'Package: saveconfig\nVersion: {VERSION}\nSection: utils\nPriority: optional\nArchitecture: all\nMaintainer: Josef\nDepends: python3 (>= 3.10), python3-requests, python3-gi, gir1.2-gtk-3.0, util-linux, libc-bin, gvfs-backends, gvfs-fuse\nDescription: Transparent configuration backup catalog for Linux Mint\n GTK 3 scan, original-file backups and SHA-256 verification.\n')
    for name in ['postinst', 'prerm', 'postrm']:
        shutil.copy2(ROOT / 'packaging' / name, control / name)
        (control / name).chmod(0o755)
    subprocess.run(['desktop-file-validate', str(desktop)], check=True)
    subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(stage), str(target)], check=True)
    import hashlib
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix('.deb.sha256').write_text(checksum + '  ' + target.name + '\n')
    print(target)

if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print('Vorbereitung fehlgeschlagen:', str(exc), file=sys.stderr)
        raise SystemExit(1)
