import json
import os
import stat
import hashlib
import tempfile
from pathlib import Path
from datetime import datetime


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, filename = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    temporary = Path(filename)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)



def source_path(value, home):
    if value == '~':
        raise ValueError('whole_home_forbidden')
    if value.startswith('~/'):
        parts = Path(value[2:])
        if '..' in parts.parts:
            raise ValueError('unsafe_path')
        return Path(home).absolute() / parts
    p = Path(value)
    if not p.is_absolute() or '..' in p.parts or not p.is_relative_to('/etc') or p == Path('/etc'):
        raise ValueError('unsafe_system_path')
    return p


def safe_source(path, home):
    # Reject symlinks in ancestors; the selected node itself may be a link.
    root = Path(home).resolve() if Path(path).is_relative_to(Path(home).absolute()) else Path('/etc').resolve()
    if not path.parent.resolve().is_relative_to(root):
        raise ValueError('symlink_ancestor')
    parent = path.parent
    while parent != root and parent != parent.parent:
        if parent.is_symlink():
            raise ValueError('symlink_ancestor')
        parent = parent.parent
    return path


def walk(path, op, exclude=None):
    op.check()
    if exclude is not None and exclude(path):return
    mode = path.lstat().st_mode
    yield path, mode
    if stat.S_ISDIR(mode):
        with os.scandir(path) as children:
            for child in sorted(children, key=lambda item: item.name):
                yield from walk(Path(child.path), op, exclude)


def open_regular(path):
    """Open an absolute file without following links in any component."""
    parts = Path(path).absolute().parts
    parent = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in parts[1:-1]:
            fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            os.close(parent)
            parent = fd
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            raise ValueError('unsupported_file')
        return fd
    finally:
        os.close(parent)


def digest(path, op):
    h = hashlib.sha256()
    with os.fdopen(open_regular(path), 'rb') as stream:
        while chunk := stream.read(1024 * 1024):
            op.check()
            h.update(chunk)
    return h.hexdigest()


def inside(path, root):
    return Path(path).resolve().is_relative_to(Path(root).resolve())


def read_json_limited(path, maximum, code):
    with os.fdopen(open_regular(Path(path)), 'rb') as source:data=source.read(maximum+1)
    if len(data)>maximum:raise ValueError(code)
    try:return json.loads(data)
    except (ValueError,UnicodeError):raise ValueError(code) from None
