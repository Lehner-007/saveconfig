import os
import socket
import stat
import time
from pathlib import Path
from .models import Entry, Cancelled
from .classification import category_for, is_codex
from .utils import source_path, safe_source, walk, now

AREAS = {'.config': 'config', '.local/share': 'data', '.local/state': 'state', '.var/app': 'data', '.cache': 'cache'}


def scan(db, home, op):
    home = Path(home).absolute()
    if not home.is_dir():
        raise ValueError('invalid_home')
    start = time.monotonic()
    with db.connect() as con:
        ident = con.execute('INSERT INTO scans VALUES(NULL,?,?,?,?,?,?)', (now(), str(home), socket.gethostname(), 'running', 0, '')).lastrowid
    entries = []
    status = 'complete'
    try:
        for row in db.catalog():
            entries.append(Entry(row['name'], row['path'], row['path_type'], bool(row['sensitive']), bool(row['enabled']), True, config_id=row['id'], category=row['category']))
        known = {e.path for e in entries}
        candidates = []
        for area, kind in AREAS.items():
            directory = home / area
            op.check()
            if directory.is_dir() and not directory.is_symlink():
                try:
                    candidates.extend(('~/' + str(p.relative_to(home)), kind) for p in directory.iterdir())
                except OSError:
                    entries.append(Entry('', '~/' + area, kind, status='error'))
        candidates.extend(('~/' + p.name, 'unknown') for p in home.iterdir() if p.name.startswith('.') and p.name not in {'.config', '.local', '.var', '.cache'})
        for path, kind in sorted(candidates):
            if path not in known and not any(path.startswith(k + '/') for k in known):
                entries.append(Entry('', path, kind, sensitive=True, selected=False, category=category_for(path, kind)))
                known.add(path)
        entries=[e for e in entries if not is_codex(e)]
        for e in entries:
            op.check()
            op.callback(e.path)
            try:
                p = safe_source(source_path(e.path, home), home)
                e.exists = os.path.lexists(p)
                if not e.exists:
                    e.selected = False
                    continue
                for node, mode in walk(p, op):
                    info = node.lstat()
                    e.modified = max(e.modified, info.st_mtime)
                    if stat.S_ISREG(mode) or stat.S_ISLNK(mode):
                        e.files += 1
                        e.size += info.st_size
                e.status = 'found' if e.known else 'new'
            except (OSError, ValueError):
                e.status, e.selected = 'error', False
                status = 'warnings'
            with db.connect() as con:
                con.execute('INSERT INTO scan_results(scan_id,config_path_id,actual_path,"exists",size,file_count,modified,status,category) VALUES(?,?,?,?,?,?,?,?,?)', (ident, e.config_id, str(source_path(e.path, home)), e.exists, e.size, e.files, e.modified, e.status, e.category))
    except Cancelled:
        status = 'cancelled'
    except Exception:
        status = 'error'
        raise
    finally:
        with db.connect() as con:
            con.execute('UPDATE scans SET status=?,duration=? WHERE id=?', (status, time.monotonic() - start, ident))
    return entries, status
