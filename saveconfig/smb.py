"""SMB via the desktop GVfs service; credentials stay in its authentication dialog."""
import os
import re
import threading
import subprocess
import time
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit


def resolve_server(server):
    if server.lower() != 'omv':return server
    try:
        result=subprocess.run(['ssh','-G','-o','CanonicalizeHostname=no','-o','PermitLocalCommand=no','omv'],capture_output=True,text=True,timeout=3,check=True)
    except (OSError,subprocess.SubprocessError):raise ValueError('smb_alias_missing') from None
    host=next((line.split(None,1)[1] for line in result.stdout.splitlines() if line.startswith('hostname ')), '')
    if not host or host.lower()=='omv' or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*',host):raise ValueError('smb_alias_missing')
    return host


def share_uri(server, share):
    server, share = server.strip(), share.strip()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*', server) or not share or any(c in share for c in '/\\\x00'):
        raise ValueError('invalid_smb')
    server=resolve_server(server)
    return 'smb://' + server.lower() + '/' + quote(share, safe='')


def local_share(uri, root=None):
    parts=urlsplit(uri)
    root=Path(root) if root is not None else Path('/run/user')/str(os.getuid())/'gvfs'
    if not root.is_dir():raise ValueError('smb_unavailable')
    for path in root.iterdir():
        if not path.name.startswith('smb-share:'):continue
        fields=dict(item.split('=',1) for item in path.name.split(':',1)[1].split(',') if '=' in item)
        if unquote(fields.get('server','')).casefold()==parts.hostname.casefold() and unquote(fields.get('share','')).casefold()==unquote(parts.path.lstrip('/')).casefold():
            if path.is_dir() and not path.is_symlink():return path
    raise ValueError('smb_unavailable')


def ensure_available(destination):
    destination=Path(destination).expanduser().absolute()
    root=Path('/run/user')/str(os.getuid())/'gvfs'
    if destination.is_relative_to(root):
        relative=destination.relative_to(root)
        if not relative.parts or not os.path.ismount(root):raise ValueError('smb_unavailable')
        share=root/relative.parts[0]
        if not share.name.startswith('smb-share:') or not share.is_dir() or share.is_symlink():raise ValueError('smb_unavailable')


def connect(uri, op, parent):
    import gi
    gi.require_version('Gtk','3.0')
    from gi.repository import Gio, Gtk, GLib
    done=threading.Event();result={};cancel=Gio.Cancellable()
    def finished(source,res):
        try:source.mount_enclosing_volume_finish(res)
        except GLib.Error as exc:
            if not exc.matches(Gio.io_error_quark(),Gio.IOErrorEnum.ALREADY_MOUNTED):result['error']=True
        finally:done.set()
    def begin():
        if cancel.is_cancelled():done.set();return False
        try:
            mount=Gtk.MountOperation.new(parent)
            mount.set_password_save(Gio.PasswordSave.NEVER)
            result['mount']=mount
            Gio.File.new_for_uri(uri).mount_enclosing_volume(Gio.MountMountFlags.NONE,mount,cancel,finished)
        except (GLib.Error,ValueError):result['error']=True;done.set()
        return False
    GLib.idle_add(begin)
    start=time.monotonic()
    try:
        while not done.wait(.1):
            op.check()
            if time.monotonic()-start>30:raise ValueError('smb_unavailable')
        op.check()
        if result.get('error'):raise ValueError('smb_unavailable')
        target=local_share(uri)
        ensure_available(target)
        return target
    finally:cancel.cancel()


def ensure_network_mount(destination, mount_point, mount_source):
    """Require an exact Linux mount identity before creating a network target."""
    destination=Path(destination).expanduser().absolute()
    mount=Path(mount_point)
    if not mount_point or not mount.is_absolute() or not mount_source or '..' in mount.parts or '..' in destination.parts or not destination.is_relative_to(mount):
        raise ValueError('network_mount_required')
    if any(p.is_symlink() for p in (destination,*destination.parents)):
        raise ValueError('network_mount_required')
    def decode(value):
        return re.sub(r'\\([0-7]{3})',lambda m:chr(int(m[1],8)),value)
    try:
        rows=Path('/proc/self/mountinfo').read_text().splitlines()
    except OSError:raise ValueError('network_mount_required') from None
    for row in rows:
        before,sep,after=row.partition(' - ')
        fields=before.split();details=after.split()
        if sep and len(fields)>4 and len(details)>1 and decode(fields[4])==str(mount):
            if details[0] not in {'cifs','smb3','nfs','nfs4'} or decode(details[1])!=mount_source:
                raise ValueError('network_mount_required')
            if not os.path.ismount(mount):raise ValueError('network_mount_required')
            return
    raise ValueError('network_mount_required')
