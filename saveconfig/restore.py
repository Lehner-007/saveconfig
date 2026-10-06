"""Read-only restore preview. Writes are deliberately deferred to phase two."""
from pathlib import Path
from .verify import load_manifest, verify
from .models import Operation
from .utils import source_path, safe_source


def preview(folder, home, op=None):
    op = op or Operation()
    manifest = load_manifest(folder,op)
    errors=verify(folder,op,write_result=False)
    result = []
    for entry in manifest['entries']:
        op.check()
        if not entry['original'].startswith('~/'):
            continue
        target = safe_source(source_path(entry['original'], home), home)
        result.append(dict(program=entry['program'], source=str(Path(folder) / entry['backup']), target=str(target), exists=target.exists() or target.is_symlink(), integrity='verification_failed' if errors else 'verified', integrity_errors=errors))
    return result
