import os
import base64
import stat
import shutil
import socket
import subprocess
import time
from pathlib import Path
from datetime import datetime
from . import VERSION
from .classification import excluded_backup
from .models import Cancelled, Operation
from .utils import source_path, safe_source, walk, now, atomic_json, digest, inside, open_regular


class InsufficientSpace(ValueError):
    def __init__(self, required, available):
        super().__init__('insufficient_space')
        self.required=required;self.available=available


def check_space(destination, required):
    available=shutil.disk_usage(destination).free
    if available<required:raise InsufficientSpace(required,available)


def inventory(op=None):
    op = op or Operation()
    result = {}
    for key, command in [('installed', ['dpkg-query', '-W', '-f=${binary:Package}\\t${Version}\\t${db:Status-Status}\\n']), ('manual', ['apt-mark', 'showmanual']), ('automatic', ['apt-mark', 'showauto'])]:
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            start = time.monotonic()
            try:
                while True:
                    op.check()
                    try:
                        stdout, _ = process.communicate(timeout=.2)
                        if process.returncode:
                            raise subprocess.CalledProcessError(process.returncode, command)
                        result[key] = stdout.splitlines()
                        break
                    except subprocess.TimeoutExpired:
                        if time.monotonic() - start > 30:
                            raise subprocess.TimeoutExpired(command, 30)
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.communicate(timeout=1)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.communicate()
        except (OSError, subprocess.SubprocessError):
            result[key] = None
    result['scope'] = 'running_system_not_alternative_home'
    return result


def copy_file(src, dst, op):
    # O_NOFOLLOW prevents substitution of the source file by a symlink.
    fd = open_regular(src)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('unsupported_file')
        with os.fdopen(fd, 'rb', closefd=False) as source, dst.open('xb') as target:
            while chunk := source.read(1024 * 1024):
                op.check()
                target.write(chunk)
        after = os.fstat(fd)
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('source_changed')
        os.chmod(dst, stat.S_IMODE(before.st_mode))
        os.utime(dst, ns=(before.st_atime_ns, before.st_mtime_ns))
        attrs = {}
        for name in os.listxattr(fd):
            value = os.getxattr(fd, name)
            os.setxattr(dst, name, value, follow_symlinks=False)
            attrs[name] = base64.b64encode(value).decode('ascii')
        return attrs
    finally:
        os.close(fd)


def _new_backup(db, home, destination, entries, op):
    home = Path(home).absolute()
    destination = Path(destination).expanduser().absolute()
    selected = [e for e in entries if e.selected and e.exists and not excluded_backup(e)]
    if not selected:
        raise ValueError('nothing_selected')
    sources = [safe_source(source_path(e.path, home), home) for e in selected]
    for src in sources:
        if inside(destination, src) or inside(src, destination):
            raise ValueError('recursive_destination')
    # Overlapping selections cannot produce duplicate target writes.
    for i, src in enumerate(sources):
        if any(src != other and src.is_relative_to(other) for other in sources):
            raise ValueError('overlapping_sources')
    destination.mkdir(parents=True, exist_ok=True)
    if not os.access(destination, os.W_OK | os.X_OK):
        raise ValueError('unwritable_destination')
    try: required = sum(node.lstat().st_size for src in sources for node, mode in walk(src, op, exclude=excluded_backup) if stat.S_ISREG(mode))
    except Cancelled: required = 0  # Persist the cancelled operation below.
    check_space(destination,required+1024*1024)
    folder = destination / datetime.now().strftime('%d.%m.%Y')
    try:
        folder.mkdir(mode=0o700)
    except FileExistsError:
        raise ValueError('daily_backup_exists') from None
    manifest = dict(format_version=1, version=VERSION, date=now(), hostname=socket.gethostname(), home=str(home), status='incomplete', file_count=0, total_size=0, entries=[], files=[], warnings=[], errors=[])
    atomic_json(folder / 'manifest.json', manifest)
    with db.connect() as con:
        ident = con.execute('INSERT INTO backups VALUES(NULL,?,?,?,?,?,?,?,?)', (manifest['date'], str(destination), str(folder), 'running', 0, 0, 0, '')).lastrowid
    try:
        for e, src in zip(selected, sources):
            op.check()
            relative = Path('home') / e.path[2:] if e.path.startswith('~/') else Path('system') / e.path.lstrip('/')
            record = dict(program=e.program, original=e.path, backup=str(relative), sensitive=e.sensitive, status='running')
            manifest['entries'].append(record)
            dirs = []
            try:
                for node, mode in walk(src, op, exclude=excluded_backup):
                    op.check()
                    safe_source(node, home)
                    rel = relative / node.relative_to(src)
                    dst = folder / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    op.callback(str(rel))
                    if stat.S_ISDIR(mode):
                        dst.mkdir(exist_ok=True)
                        metadata=dict(path=str(rel), type='directory', mode=stat.S_IMODE(mode))
                        dirs.append((node, dst, metadata))
                        manifest['files'].append(metadata)
                    elif stat.S_ISLNK(mode):
                        link = os.readlink(node)
                        dst.symlink_to(link)
                        manifest['files'].append(dict(path=str(rel), type='symlink', target=link))
                        manifest['file_count'] += 1
                    elif stat.S_ISREG(mode):
                        attrs = copy_file(node, dst, op)
                        size = dst.stat().st_size
                        manifest['files'].append(dict(path=str(rel), type='file', size=size, sha256=digest(dst, op), mode=stat.S_IMODE(mode), xattrs=attrs or {}))
                        manifest['file_count'] += 1
                        manifest['total_size'] += size
                    else:
                        manifest['warnings'].append(dict(path=str(rel), code='unsupported_file'))
                for original, target, metadata in reversed(dirs):
                    op.check()
                    attrs={name:os.getxattr(original,name,follow_symlinks=False) for name in os.listxattr(original,follow_symlinks=False)}
                    shutil.copystat(original, target, follow_symlinks=False)
                    for name,value in attrs.items():os.setxattr(target,name,value,follow_symlinks=False)
                    actual={name:os.getxattr(target,name,follow_symlinks=False) for name in os.listxattr(target,follow_symlinks=False)}
                    if actual!=attrs:raise ValueError('directory_metadata_failed')
                    metadata['xattrs']={name:base64.b64encode(value).decode('ascii') for name,value in attrs.items()}
                record['status'] = 'complete'
            except (OSError, ValueError) as exc:
                record['status'] = 'error'
                manifest['errors'].append(dict(path=e.path, code=str(exc) if isinstance(exc, ValueError) else type(exc).__name__))
        packages = inventory(op)
        atomic_json(folder / 'packages.json', packages)
        if any(packages.get(key) is None for key in ('installed', 'manual', 'automatic')):
            manifest['warnings'].append(dict(code='inventory_incomplete'))
        manifest['status'] = 'warnings' if manifest['errors'] or manifest['warnings'] else 'complete'
    except Cancelled:
        manifest['status'] = 'cancelled'
    except (OSError, ValueError) as exc:
        manifest['status'] = 'incomplete'
        manifest['errors'].append(dict(code=str(exc) if isinstance(exc, ValueError) else type(exc).__name__))
    finally:
        if op.cancel.is_set() and manifest['status'] in ('complete', 'warnings'):
            manifest['status'] = 'cancelled'
        with db.connect() as con:
            con.execute('UPDATE backups SET status=?,file_count=?,total_size=? WHERE id=?', (manifest['status'], manifest['file_count'], manifest['total_size'], ident))
        # Failure to finalize never promotes the initially incomplete manifest.
        try:
            db.snapshot(folder / 'saveconfig.db')
            final_op = Operation()  # Finalize metadata safely even after cancellation.
            manifest['database_sha256'] = digest(folder / 'saveconfig.db', final_op)
            manifest['packages_sha256'] = digest(folder / 'packages.json', final_op) if (folder / 'packages.json').exists() else None
            atomic_json(folder / 'manifest.json', manifest)
        except (OSError, ValueError):
            with db.connect() as con:
                con.execute('UPDATE backups SET status=? WHERE id=?', ('incomplete', ident))
            raise
    return folder, manifest


def _daily_backup(db, home, destination, entries, op):
    """Ergänzt neue Bereiche im Tagesstand; veröffentlicht nur vollständige Ergänzungen."""
    import tempfile
    import sqlite3
    import ctypes
    from .verify import load_manifest, verify
    destination=Path(destination).expanduser().absolute()
    day=destination/datetime.now().strftime('%d.%m.%Y')
    if not day.exists() and not day.is_symlink():
        return _new_backup(db,home,destination,entries,op)
    if day.is_symlink() or not day.is_dir():raise ValueError('unsafe_manifest')
    old=load_manifest(day,op)
    if old.get('home')!=str(Path(home).absolute()) or old.get('hostname')!=socket.gethostname():
        raise ValueError('daily_backup_other_source')
    selected=[e for e in entries if e.selected and e.exists and not excluded_backup(e)]
    if not selected:raise ValueError('nothing_selected')
    existing=[Path(e['backup']) for e in old['entries']]
    additions=[]
    for entry in selected:
        relative=Path('home')/entry.path[2:] if entry.path.startswith('~/') else Path('system')/entry.path.lstrip('/')
        if any(relative==p or relative.is_relative_to(p) for p in existing):continue
        if any(p.is_relative_to(relative) for p in existing):raise ValueError('overlapping_sources')
        additions.append(entry)
    if verify(day,op):raise ValueError('daily_backup_invalid')
    if not additions:
        result=dict(old);result['reused']=True;result['skipped_entries']=[e.path for e in selected];return day,result
    required=sum(node.lstat().st_size for e in additions for node,mode in walk(safe_source(source_path(e.path,Path(home)),Path(home)),op,exclude=excluded_backup) if stat.S_ISREG(mode))
    check_space(destination,2*required+old['total_size']+1024*1024)
    with tempfile.TemporaryDirectory(prefix='.saveconfig-add-',dir=destination) as temporary:
        root=Path(temporary)
        try:
            fresh,new=_new_backup(db,home,root/'new',additions,op)
            op.check()
            if new['status'] not in ('complete','warnings') or new['errors']:
                raise ValueError('daily_backup_add_failed')
            merged=root/'merged'
            def copy(source,target):
                op.check();op.callback(str(Path(source).name));return shutil.copy2(source,target)
            shutil.copytree(day,merged,symlinks=True,copy_function=copy)
            for entry in new['entries']:
                relative=Path(entry['backup']);src=fresh/relative;target=merged/relative
                target.parent.mkdir(parents=True,exist_ok=True)
                if src.is_symlink():target.symlink_to(os.readlink(src))
                elif src.is_dir():shutil.copytree(src,target,symlinks=True,copy_function=copy)
                else:copy(src,target)
            for name in ('saveconfig.db','packages.json'):copy(fresh/name,merged/name)
            combined=dict(old,version=VERSION,date=now(),entries=old['entries']+new['entries'],files=old['files']+new['files'],
                          file_count=old['file_count']+new['file_count'],total_size=old['total_size']+new['total_size'],
                          warnings=old['warnings']+new['warnings'],errors=[],database_sha256=new['database_sha256'],packages_sha256=new['packages_sha256'])
            with sqlite3.connect(merged/'saveconfig.db') as saved:
                saved.execute('DELETE FROM backups WHERE backup_directory=?',(str(fresh),))
                saved.execute('UPDATE backups SET backup_date=?,status=?,file_count=?,total_size=?,verified=0 WHERE backup_directory=?',
                              (combined['date'],'warnings' if combined['warnings'] else 'complete',combined['file_count'],combined['total_size'],str(day)))
            combined['database_sha256']=digest(merged/'saveconfig.db',op)
            combined['status']='warnings' if combined['warnings'] else 'complete'
            atomic_json(merged/'manifest.json',combined)
            if verify(merged,op):raise ValueError('daily_backup_add_failed')
            (merged/'verification.json').unlink(missing_ok=True)
            op.check()
            # Linux rename exchange keeps either complete directory visible, including on failure.
            libc=ctypes.CDLL(None,use_errno=True)
            if libc.renameat2(-100,os.fsencode(day),-100,os.fsencode(merged),2):
                raise OSError(ctypes.get_errno(),'Could not publish daily backup')
            with db.connect() as con:
                con.execute('DELETE FROM backups WHERE backup_directory=?',(str(fresh),))
                con.execute('UPDATE backups SET backup_date=?,status=?,file_count=?,total_size=?,verified=0 WHERE backup_directory=?',
                            (combined['date'],combined['status'],combined['file_count'],combined['total_size'],str(day)))
            return day,combined
        finally:
            with db.connect() as con:
                con.execute('DELETE FROM backups WHERE backup_directory=?',(str(root/'new'/day.name),))



def backup(db,home,destination,entries,op,*,target_kind="local",mount_point="",mount_source=""):
    import fcntl
    from .smb import ensure_available
    destination=Path(destination).expanduser().absolute()
    ensure_available(destination)
    if target_kind == "network":
        from .smb import ensure_network_mount
        ensure_network_mount(destination,mount_point,mount_source)
    elif target_kind != "local":raise ValueError("network_mount_required")
    elif destination.is_relative_to(Path("/mnt/omv-server")):
        raise ValueError("network_mount_required")
    destination.mkdir(parents=True,exist_ok=True)
    descriptor=os.open(destination,os.O_RDONLY|os.O_DIRECTORY)
    try:
        try:fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('backup_busy') from None
        return _daily_backup(db,home,destination,entries,op)
    finally:os.close(descriptor)
