import json
import os
import socket
import sqlite3
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from saveconfig.database import Database
from saveconfig.settings import Settings
from saveconfig.scanner import scan
from saveconfig.backup import backup
from saveconfig.verify import verify
from saveconfig.restore import preview
from saveconfig.models import Operation
from saveconfig.languages import Languages

ROOT = Path(__file__).resolve().parent.parent

class CoreTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'work').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        self.root = Path(self.temp.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.target = self.root / 'backups'
        self.db = Database(self.root / 'state/saveconfig.db')
        folder = self.home / '.config/filezilla'
        folder.mkdir(parents=True)
        (folder / 'sitemanager.xml').write_text('<test/>')
        (folder / 'empty').mkdir()
        (folder / 'space ü.txt').write_bytes(b'abc')
        os.chmod(folder / 'space ü.txt', 0o640)
        self.external = self.root / 'external'
        self.external.mkdir()
        (self.external / 'excluded').write_text('outside')
        (folder / 'external-link').symlink_to(self.external, target_is_directory=True)
        (folder / 'broken').symlink_to('missing')
        self.op = Operation()

    def tearDown(self):
        self.temp.cleanup()

    def entries(self):
        entries, status = scan(self.db, self.home, self.op)
        self.assertEqual(status, 'complete')
        for e in entries:
            e.selected = e.path == '~/.config/filezilla'
        return entries

    def snapshot(self):
        with patch('saveconfig.backup.inventory', return_value={'installed': [], 'manual': [], 'automatic': []}):
            return backup(self.db, self.home, self.target, self.entries(), self.op)

    def test_roundtrip_layout_attributes(self):
        folder, m = self.snapshot()
        self.assertEqual(m['status'], 'complete')
        p = folder / 'home/.config/filezilla'
        self.assertEqual((p / 'sitemanager.xml').read_text(), '<test/>')
        self.assertTrue((p / 'empty').is_dir())
        self.assertEqual((p / 'space ü.txt').stat().st_mode & 0o777, 0o640)
        self.assertTrue((p / 'external-link').is_symlink())
        self.assertEqual(os.readlink(p / 'external-link'), str(self.external))
        self.assertFalse(any('excluded' in r['path'] for r in m['files']))
        self.assertEqual(verify(folder, self.op), [])
        self.assertEqual(folder.stat().st_mode & 0o777, 0o700)
        with sqlite3.connect(folder / 'saveconfig.db') as db:
            self.assertEqual(db.execute('SELECT status FROM backups').fetchone()[0], 'complete')

    def test_unknowns_cache_sensitive(self):
        (self.home / '.config/unknown').mkdir()
        (self.home / '.cache/app').mkdir(parents=True)
        (self.home / '.local/share/big').mkdir(parents=True)
        (self.home / '.oddrc').write_text('neutral')
        entries, _ = scan(self.db, self.home, self.op)
        bypath = {e.path: e for e in entries}
        for p in ['~/.config/unknown', '~/.cache/app', '~/.local/share/big', '~/.oddrc']:
            self.assertFalse(bypath[p].selected)
            self.assertTrue(bypath[p].sensitive)
        self.assertTrue(bypath['~/.config/filezilla'].sensitive)
        self.assertEqual(bypath['~/.cache/app'].kind, 'cache')
        self.assertFalse(bypath['~/.ssh'].exists)

    def test_catalog_confirmation_persistence(self):
        self.db.learn('User app', '', '~/.oddrc', 'config', False, True, 'note')
        row = next(r for r in self.db.catalog() if r['path'] == '~/.oddrc')
        self.assertEqual(row['name'], 'User app')
        self.assertTrue(row['enabled'])

    def test_recursive_targets(self):
        entries = self.entries()
        for target in [self.home / '.config/filezilla', self.home / '.config/filezilla/backup', self.home]:
            with self.assertRaisesRegex(ValueError, 'recursive'):
                backup(self.db, self.home, target, entries, self.op)

    def test_cancel_scan(self):
        self.op.cancel.set()
        _, status = scan(self.db, self.home, self.op)
        self.assertEqual(status, 'cancelled')
        with self.db.connect() as db:
            self.assertEqual(db.execute('SELECT status FROM scans').fetchone()[0], 'cancelled')

    def test_cancel_backup(self):
        entries = self.entries()
        self.op.cancel.set()
        folder, m = backup(self.db, self.home, self.target, entries, self.op)
        self.assertEqual(m['status'], 'cancelled')
        self.assertEqual(json.loads((folder / 'manifest.json').read_text())['status'], 'cancelled')
        self.assertIn('incomplete_backup', verify(folder, Operation()))

    def test_large_file_cancel_mid_copy(self):
        p = self.home / '.config/filezilla/large'
        p.write_bytes(b'x' * (4 * 1024 * 1024))
        entries = self.entries()
        op = Operation(lambda name: op.cancel.set() if name.endswith('/large') else None)
        folder, m = backup(self.db, self.home, self.target, entries, op)
        self.assertEqual(m['status'], 'cancelled')
        self.assertEqual(json.loads((folder / 'manifest.json').read_text())['status'], 'cancelled')

    def test_file_damage_missing_checksum(self):
        for mode in ['damage', 'missing']:
            folder, m = backup(self.db,self.home,self.target/mode,self.entries(),self.op)
            p = folder / 'home/.config/filezilla/space ü.txt'
            if mode == 'damage':
                p.write_bytes(b'xyz')
            else:
                p.unlink()
            self.assertIn('home/.config/filezilla/space ü.txt', verify(folder, self.op))

    def test_manifest_damage_traversal(self):
        folder, m = self.snapshot()
        (folder / 'manifest.json').write_text('{')
        with self.assertRaises(ValueError):
            verify(folder, self.op)
        m['files'][0]['path'] = '../../escape'
        (folder / 'manifest.json').write_text(json.dumps(m))
        with self.assertRaises(ValueError):
            verify(folder, self.op)

    def test_manifest_symlink_ancestor(self):
        folder, m = self.snapshot()
        p = folder / 'home/.config/filezilla'
        import shutil
        shutil.rmtree(p)
        p.symlink_to(self.external, target_is_directory=True)
        with self.assertRaises(ValueError):
            verify(folder, self.op)

    def test_source_symlink_ancestor(self):
        import shutil
        shutil.rmtree(self.home / '.config')
        (self.home / '.config').symlink_to(self.external, target_is_directory=True)
        entries, _ = scan(self.db, self.home, self.op)
        self.assertEqual(next(e for e in entries if e.path == '~/.config/filezilla').status, 'error')

    def test_collision(self):
        folder1, _ = self.snapshot()
        from datetime import datetime
        self.assertEqual(folder1.name,datetime.now().strftime('%d.%m.%Y'))
        before=(folder1/'manifest.json').read_bytes()
        repeated,_=self.snapshot()
        self.assertEqual(repeated,folder1)
        self.assertEqual((folder1/'manifest.json').read_bytes(),before)
        self.assertEqual(list(self.target.iterdir()),[folder1])

    def test_daily_addition_and_failed_addition_preserve_previous(self):
        from saveconfig.models import Entry
        folder,first=self.snapshot()
        original=(folder/'home/.config/filezilla/space ü.txt').read_bytes()
        new=self.home/'.config/new-area';new.mkdir();(new/'config').write_text('new settings')
        entry=Entry('New','~/.config/new-area',selected=True,exists=True,size=12)
        with patch('saveconfig.backup.inventory',return_value=dict(installed=[],manual=[],automatic=[])):
            result,manifest=backup(self.db,self.home,self.target,[entry],self.op)
        self.assertEqual(result,folder)
        self.assertEqual((folder/'home/.config/new-area/config').read_text(),'new settings')
        self.assertEqual((folder/'home/.config/filezilla/space ü.txt').read_bytes(),original)
        self.assertEqual(verify(folder,self.op),[])
        previous=(folder/'manifest.json').read_bytes()
        failed=self.home/'.config/failed';failed.mkdir();(failed/'config').write_text('fail')
        entry=Entry('Failed','~/.config/failed',selected=True,exists=True,size=4)
        with patch('saveconfig.backup.copy_file',side_effect=OSError('unavailable')),patch('saveconfig.backup.inventory',return_value=dict(installed=[],manual=[],automatic=[])):
            with self.assertRaisesRegex(ValueError,'daily_backup_add_failed'):
                backup(self.db,self.home,self.target,[entry],self.op)
        self.assertEqual((folder/'manifest.json').read_bytes(),previous)
        self.assertFalse((folder/'home/.config/failed').exists())
        self.assertEqual(verify(folder,self.op),[])
        self.assertEqual([p for p in self.target.iterdir() if p.is_dir()],[folder])
        cancel_area=self.home/'.config/cancel-area';cancel_area.mkdir();(cancel_area/'config').write_text('cancel')
        entry=Entry('Cancel','~/.config/cancel-area',selected=True,exists=True,size=6)
        cancelling=Operation(lambda message:cancelling.cancel.set() if message=='home/.config/cancel-area/config' else None)
        from saveconfig.models import Cancelled
        with self.assertRaises(Cancelled):backup(self.db,self.home,self.target,[entry],cancelling)
        self.assertEqual((folder/'manifest.json').read_bytes(),previous)
        self.assertEqual(verify(folder,self.op),[])
        with self.db.connect() as con:
            paths=[row['backup_directory'] for row in con.execute('SELECT backup_directory FROM backups')]
        self.assertEqual(paths,[str(folder)])


    def test_unreachable_target(self):
        bad = self.root / 'file'
        bad.write_text('not directory')
        with self.assertRaises(OSError):
            backup(self.db, self.home, bad / 'target', self.entries(), self.op)

    def test_disconnected_target_finalization(self):
        # Simulate storage I/O failure without touching a real mount.
        with patch('saveconfig.backup.atomic_json', side_effect=[None, OSError('offline'), OSError('offline')]), patch('saveconfig.backup.inventory', return_value={}):
            with self.assertRaises(OSError):
                backup(self.db, self.home, self.target, self.entries(), self.op)

    def test_missing_read_permission(self):
        with patch('saveconfig.backup.copy_file', side_effect=PermissionError()):
            folder, m = self.snapshot()
        self.assertEqual(m['status'], 'warnings')
        self.assertTrue(m['errors'])
        self.assertIn('backup_errors', verify(folder, self.op))

    def test_db_corruption(self):
        folder, _ = self.snapshot()
        (folder / 'saveconfig.db').write_bytes(b'bad')
        self.assertIn('saveconfig.db', verify(folder, self.op))

    def test_empty_selection(self):
        entries = self.entries()
        for e in entries:
            e.selected = False
        with self.assertRaisesRegex(ValueError, 'nothing_selected'):
            backup(self.db, self.home, self.target, entries, self.op)

    def test_restore_preview_no_write(self):
        folder, _ = self.snapshot()
        alternative = self.root / 'new-home'
        alternative.mkdir()
        rows = preview(folder, alternative)
        self.assertEqual(rows[0]['target'], str(alternative / '.config/filezilla'))
        self.assertFalse(rows[0]['exists'])
        self.assertEqual(list(alternative.iterdir()), [])

    def test_settings_language(self):
        settings = Settings(self.root / 'settings')
        settings.data['destination'] = str(self.target)
        settings.save()
        loaded = Settings(settings.root)
        self.assertEqual(loaded.data['destination'], str(self.target))
        languages = Languages(loaded)
        self.assertEqual(languages.packs['de']['strings'].keys(), languages.packs['en']['strings'].keys())
        pack = dict(languages.packs['en'])
        pack.update(code='xx', name='Example',help_html='<html><body><h1>Offline help</h1></body></html>')
        languages.install(pack)
        with self.assertRaises(ValueError):
            languages.install(pack)
        bad = dict(pack, code='../bad')
        with self.assertRaises(ValueError):
            languages.install(bad)

    def test_source_unchanged(self):
        before = {str(p.relative_to(self.home)): p.lstat().st_mtime_ns for p in self.home.rglob('*')}
        self.snapshot()
        after = {str(p.relative_to(self.home)): p.lstat().st_mtime_ns for p in self.home.rglob('*')}
        self.assertEqual(before, after)

if __name__ == '__main__':
    unittest.main()
