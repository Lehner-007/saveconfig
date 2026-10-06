#!/usr/bin/env python3
import argparse
import json
import time
import sqlite3
from pathlib import Path
from saveconfig import VERSION, AUTHOR
from saveconfig.settings import Settings
from saveconfig.database import Database
from saveconfig.models import Operation
from saveconfig.scanner import scan
from saveconfig.backup import backup
from saveconfig.verify import verify
from saveconfig.logging_setup import setup


def main():
    parser = argparse.ArgumentParser(description='saveconfig – configuration scan, backup and verification / Konfigurationen suchen, sichern und prüfen')
    parser.add_argument('--version', action='version', version=f'saveconfig {VERSION}')
    parser.add_argument('--author', action='version', version=AUTHOR, help='Show author / Autor anzeigen')
    parser.add_argument('--state-home', type=Path, help='Isolated application settings/data home for development and tests')
    parser.add_argument('--home', type=Path, help='Source home; defaults to Path.home()')
    sub = parser.add_subparsers(dest='command')
    sub.add_parser('scan', help='Read-only scan; JSON output')
    copy = sub.add_parser('backup', help='Backup explicitly selected catalog or discovered paths')
    copy.add_argument('--destination', type=Path, required=True)
    copy.add_argument('--target-kind',choices=['local','network'],default='local')
    copy.add_argument('--mount-point',default='')
    copy.add_argument('--mount-source',default='',help='Expected mount source, e.g. //server/share')
    copy.add_argument('--path', action='append', required=True, help='e.g. ~/.config/filezilla; shell quote the path')
    copy.add_argument('--allow-sensitive', action='store_true', help='Explicit consent to copy potentially sensitive data')
    check = sub.add_parser('verify', help='Verify a backup directory')
    check.add_argument('folder', type=Path)
    args = parser.parse_args()
    settings = Settings(args.state_home)
    logger = setup(settings.root)
    op = Operation()
    home = args.home or Path(settings.data['home'])
    exit_code=1
    started=time.monotonic()
    try:
        try:settings.remember_installed_locations()
        except (OSError,ValueError):logger.warning('Speicherorte konnten nicht vorgemerkt werden')
        try:db = Database(settings.db_path)
        except sqlite3.Error:
            from saveconfig.languages import Languages
            message=Languages(settings).text('catalog_unavailable').format(path=settings.db_path)
            logger.error('%s',message)
            if args.command is None:
                from saveconfig.gui import Gtk
                dialog=Gtk.MessageDialog(message_type=Gtk.MessageType.ERROR,buttons=Gtk.ButtonsType.CLOSE,text=message)
                dialog.run();dialog.destroy()
            else:print(json.dumps(dict(status='error',code='catalog_unavailable',path=str(settings.db_path),message=message),ensure_ascii=False))
            return 1
        if args.command == 'scan':
            entries, status = scan(db, home, op)
            print(json.dumps(dict(status=status, entries=[e.data() for e in entries]), ensure_ascii=False, indent=2))
            exit_code=0 if status == 'complete' else 1
            return exit_code
        if args.command == 'backup':
            entries, status = scan(db, home, op)
            selected = set(args.path)
            available = {e.path for e in entries if e.exists and e.status != 'error'}
            if not selected.issubset(available):
                raise ValueError('unknown_or_unreadable_path')
            for e in entries:
                e.selected = e.path in selected
            if any(e.selected and e.sensitive for e in entries) and not args.allow_sensitive:
                raise ValueError('sensitive_consent_required')
            folder, manifest = backup(db, home, args.destination, entries, op,target_kind=args.target_kind,mount_point=args.mount_point,mount_source=args.mount_source)
            print(json.dumps(dict(folder=str(folder), status=manifest['status'],reused=bool(manifest.get('reused')),existing_areas_unchanged=bool(manifest.get('reused')),backup_date=manifest['date'])))
            exit_code=0 if manifest['status'] == 'complete' else 1
            return exit_code
        if args.command == 'verify':
            errors = verify(args.folder, op)
            print(json.dumps(dict(verified=not errors, errors=errors)))
            exit_code=int(bool(errors))
            return exit_code
        from saveconfig.gui import Window, Gtk
        Window(settings, db, logger)
        Gtk.main()
        exit_code=0
        return exit_code
    except KeyboardInterrupt:
        op.cancel.set()
        exit_code=130
        return exit_code
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps(dict(status='error', code=str(exc) if isinstance(exc, ValueError) else type(exc).__name__)))
        return exit_code
    finally:
        from saveconfig.languages import Languages
        logger.info(Languages(settings).text('ended').format(version=VERSION,code=exit_code,duration=time.monotonic()-started))


if __name__ == '__main__':
    raise SystemExit(main())
