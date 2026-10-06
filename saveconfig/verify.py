import json
import base64
import os
import stat
import sqlite3
import re
from pathlib import Path
from .utils import digest, atomic_json, now, open_regular, walk
from .models import Operation


MAX_MANIFEST_BYTES = 512 * 1024 * 1024


def contained(folder, value):
    folder=Path(folder).absolute()
    if not isinstance(value,str) or not value or '\x00' in value:
        raise ValueError('unsafe_manifest_path')
    rel=Path(value)
    if rel.is_absolute() or not rel.parts or any(part in ('..','.') for part in value.split('/')):
        raise ValueError('unsafe_manifest_path')
    path=folder/rel
    for parent in path.parents:
        if parent==folder:break
        if parent==parent.parent or not parent.is_relative_to(folder):raise ValueError('unsafe_manifest_path')
        if parent.is_symlink():raise ValueError('symlink_ancestor')
    return path


def load_manifest(folder, op=None):
    op = op or Operation()
    op.check()
    op.callback("manifest.json")
    folder=Path(folder).resolve()
    with os.fdopen(open_regular(folder/'manifest.json'),'rb') as source:
        chunks=[]; total=0
        while True:
            op.check()
            chunk=source.read(min(1024*1024, MAX_MANIFEST_BYTES+1-total))
            if not chunk:break
            chunks.append(chunk);total+=len(chunk)
            if total>MAX_MANIFEST_BYTES:raise ValueError('manifest_too_large')
        raw=b''.join(chunks)
        del chunks
    op.check()
    if len(raw)>MAX_MANIFEST_BYTES:raise ValueError('manifest_too_large')
    try:m=json.loads(raw)
    except (ValueError,UnicodeError):raise ValueError('invalid_manifest') from None
    op.check()
    def integer(value):return type(value) is int and value>=0
    def checksum(value):return isinstance(value,str) and bool(re.fullmatch('[0-9a-f]{64}',value))
    if not isinstance(m,dict) or type(m.get('format_version')) is not int or m['format_version']!=1:
        raise ValueError('invalid_manifest')
    if m.get('status') not in ('complete','warnings','incomplete','cancelled') or not all(isinstance(m.get(k),str) for k in ('home','hostname','date')):
        raise ValueError('invalid_manifest')
    if not Path(m['home']).is_absolute() or not all(integer(m.get(k)) for k in ('file_count','total_size')):
        raise ValueError('invalid_manifest')
    if not all(isinstance(m.get(k),list) for k in ('files','entries','warnings','errors')):
        raise ValueError('invalid_manifest')
    for key in ('database_sha256','packages_sha256'):
        if m.get(key) is not None and not checksum(m[key]):raise ValueError('invalid_manifest')
    seen=set()
    for record in m['files']:
        op.check()
        if not isinstance(record,dict):raise ValueError('invalid_manifest')
        path=contained(folder,record.get('path'))
        value=str(path.relative_to(folder))
        kind=record.get('type')
        if value in seen or kind not in ('file','directory','symlink'):raise ValueError('invalid_manifest')
        seen.add(value)
        if kind in ('file','directory') and (not integer(record.get('mode')) or record['mode']>0o7777):raise ValueError('invalid_manifest')
        if kind=='file' and (not integer(record.get('size')) or not checksum(record.get('sha256'))):raise ValueError('invalid_manifest')
        if kind=='symlink' and (not isinstance(record.get('target'),str) or '\x00' in record['target']):raise ValueError('invalid_manifest')
        if 'xattrs' in record and (not isinstance(record['xattrs'],dict) or not all(isinstance(k,str) and isinstance(v,str) for k,v in record['xattrs'].items())):raise ValueError('invalid_manifest')
    entries=set()
    for entry in m['entries']:
        op.check()
        if not isinstance(entry,dict) or not all(isinstance(entry.get(k),str) for k in ('program','original','backup','status')):raise ValueError('invalid_manifest')
        path=contained(folder,entry['backup'])
        if entry['backup'] in entries or entry['status'] not in ('complete','error','running'):raise ValueError('invalid_manifest')
        entries.add(entry['backup'])
        original=entry['original']
        if not (original.startswith('~/') or original.startswith('/etc/')) or '..' in Path(original).parts:raise ValueError('invalid_manifest')
        if type(entry.get('sensitive')) is not bool:raise ValueError('invalid_manifest')
        expected=Path('home')/original[2:] if original.startswith('~/') else Path('system')/original.lstrip('/')
        if path.relative_to(folder)!=expected:raise ValueError('invalid_manifest')
    if not all(isinstance(item,dict) for item in m['warnings']+m['errors']):raise ValueError('invalid_manifest')
    return m


def verify(folder, op, write_result=True):
    folder = Path(folder).resolve()
    m = load_manifest(folder, op)
    errors = []
    if m.get('status') not in ('complete', 'warnings'):
        errors.append('incomplete_backup')
    for filename, checksum in [('saveconfig.db', m.get('database_sha256')), ('packages.json', m.get('packages_sha256'))]:
        op.check()
        path = contained(folder, filename)
        try:
            if path.is_symlink() or not path.is_file() or not checksum or digest(path, op) != checksum:
                errors.append(filename)
        except OSError:
            errors.append(filename)
    database = folder / 'saveconfig.db'
    if database.is_file() and not database.is_symlink():
        try:
            with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
                if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    errors.append('database_integrity')
        except sqlite3.Error:
            errors.append('database_integrity')
    for record in m['files']:
        op.check()
        p = contained(folder, record['path'])
        op.callback(record['path'])
        try:
            mode = p.lstat().st_mode
            kind = record['type']
            valid = False
            if kind == 'symlink':
                valid = stat.S_ISLNK(mode) and os.readlink(p) == record['target']
            elif kind == 'directory':
                valid = stat.S_ISDIR(mode) and stat.S_IMODE(mode) == record['mode']
            elif kind == 'file':
                valid = stat.S_ISREG(mode) and p.stat().st_size == record['size'] and stat.S_IMODE(mode) == record['mode'] and digest(p, op) == record['sha256']
            if valid and kind in ('file','directory') and 'xattrs' in record:
                fd = os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW) if kind=='directory' else open_regular(p)
                try:
                    actual = {name: base64.b64encode(os.getxattr(fd, name)).decode('ascii') for name in os.listxattr(fd)}
                    valid = actual == record['xattrs']
                finally:
                    os.close(fd)
            if not valid:
                errors.append(record['path'])
        except OSError:
            errors.append(record['path'])
    expected={str(contained(folder,r['path']).relative_to(folder)) for r in m['files']}
    allowed={'manifest.json','saveconfig.db','packages.json','verification.json'}|expected
    for value in expected:
        allowed.update(str(p) for p in Path(value).parents if str(p)!='.')
    try:
        for path,_ in walk(folder,op):
            if path!=folder and str(path.relative_to(folder)) not in allowed:errors.append('extra:'+str(path.relative_to(folder)))
    except OSError:errors.append('inventory_unreadable')
    if sum(r['type'] != 'directory' for r in m['files']) != m.get('file_count') or sum(r.get('size', 0) for r in m['files']) != m.get('total_size'):
        errors.append('manifest_totals')
    if m.get('errors'):
        errors.append('backup_errors')
    # A separate sidecar keeps the original manifest and database immutable.
    if write_result:atomic_json(folder / 'verification.json', dict(date=now(), verified=not errors, errors=errors))
    return errors
