import tempfile
import unittest
import sqlite3
from pathlib import Path
from saveconfig.database import Database
from saveconfig.scanner import scan
from saveconfig.models import Operation
from saveconfig.classification import FILTER_DEFAULTS, visible
from saveconfig.settings import Settings
from saveconfig.gui import Window, Gtk, GLib
from saveconfig.logging_setup import setup

ROOT = Path(__file__).resolve().parent.parent

class ClassificationTests(unittest.TestCase):
    def test_classification_scan_preservation_and_manual(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as temp:
            root = Path(temp)
            home = root/'home'
            (home/'.config/cinnamon').mkdir(parents=True)
            (home/'.config/testprogramm').mkdir()
            (home/'.cache/mozilla').mkdir(parents=True)
            for name in ('cinnamon-monitors.xml','cinnamon-monitors.xml~','other.bak','other.backup','other.old','other.orig'):
                (home/'.config'/name).write_text('sample')
            db = Database(root/'catalog.db')
            before = {str(p):p.lstat().st_mtime_ns for p in home.rglob('*')}
            entries,status = scan(db,home,Operation())
            self.assertEqual(status,'complete')
            bypath = {e.path:e for e in entries}
            for path in ('~/.config/cinnamon','~/.config/cinnamon-monitors.xml'):
                entry=bypath[path]
                self.assertEqual((entry.program,entry.category,entry.kind),('Cinnamon','system_desktop','config'))
                self.assertFalse(visible(entry,FILTER_DEFAULTS))
            for path in ('~/.config/cinnamon-monitors.xml~','~/.config/other.bak','~/.config/other.backup','~/.config/other.old','~/.config/other.orig'):
                entry=bypath[path]
                self.assertEqual(entry.category,'backup_file')
                self.assertFalse(entry.selected)
                self.assertFalse(visible(entry,FILTER_DEFAULTS))
            self.assertEqual(bypath['~/.cache/mozilla'].category,'cache')
            self.assertFalse(bypath['~/.cache/mozilla'].selected)
            self.assertTrue(visible(bypath['~/.config/testprogramm'],FILTER_DEFAULTS))
            self.assertEqual(before,{str(p):p.lstat().st_mtime_ns for p in home.rglob('*')})
            with db.connect() as con:
                count=con.execute('SELECT COUNT(*) FROM scan_results').fetchone()[0]
                self.assertTrue(con.execute("SELECT category FROM scan_results WHERE actual_path LIKE '%cinnamon-monitors.xml~'").fetchone())
            states=[e.selected for e in entries]
            for key in FILTER_DEFAULTS:
                filters=dict(FILTER_DEFAULTS);filters[key]=not filters[key]
                [visible(e,filters) for e in entries]
            self.assertEqual(states,[e.selected for e in entries])
            with db.connect() as con:
                self.assertEqual(count,con.execute('SELECT COUNT(*) FROM scan_results').fetchone()[0])
            db.classify('~/.config/testprogramm','program_data','data')
            entries,_=scan(Database(db.path),home,Operation())
            entry=next(e for e in entries if e.path=='~/.config/testprogramm')
            self.assertEqual(entry.category,'program_data')
            self.assertTrue(entry.known)
            db.classify('~/.config/testprogramm','ignored','unknown')
            entries,_=scan(Database(db.path),home,Operation())
            self.assertFalse(visible(next(e for e in entries if e.path=='~/.config/testprogramm'),dict.fromkeys(FILTER_DEFAULTS,True)))

    def test_old_db_migration(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as temp:
            path=Path(temp)/'old.db'
            with sqlite3.connect(path) as con:
                con.executescript('CREATE TABLE programs(id INTEGER PRIMARY KEY,name TEXT UNIQUE,package_name TEXT,package_type TEXT,description TEXT,enabled INTEGER,created_at TEXT,updated_at TEXT); CREATE TABLE config_paths(id INTEGER PRIMARY KEY,program_id INTEGER,path TEXT UNIQUE,path_type TEXT,required INTEGER,sensitive INTEGER,enabled INTEGER,notes TEXT); INSERT INTO programs VALUES(1,"Custom","","unknown","",1,"",""); INSERT INTO config_paths VALUES(1,1,"~/.custom","config",0,0,1,"keep");')
            db=Database(path)
            custom=next(row for row in db.catalog() if row['path']=='~/.custom')
            self.assertEqual(custom['notes'],'keep')
            self.assertEqual(custom['category'],'program')

    @unittest.skipUnless(Gtk.init_check()[0], 'No display')
    def test_single_settings_menu_and_filter(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as temp:
            root=Path(temp);home=root/'home';home.mkdir()
            (home/'.cache/app').mkdir(parents=True)
            settings=Settings(root/'state');settings.data['home']=str(home)
            window=Window(settings,Database(settings.db_path),setup(settings.root))
            self.assertEqual(sum(key=='settings' for _,key in window.menu_labels),1)
            self.assertFalse(any(key in ('language','install_languages') for _,key in window.menu_labels))
            window.entries,_=scan(window.db,home,Operation())
            window.refresh()
            count=len(window.model)
            states=[e.selected for e in window.entries]
            self.assertNotIn('cache',window.filter_widgets)
            self.assertEqual(len(window.model),count)
            self.assertEqual(states,[e.selected for e in window.entries])
            def apply_dialog():
                for dialog in Gtk.Window.list_toplevels():
                    if isinstance(dialog,Gtk.Dialog):
                        # Apply the initially configured defaults; clears the temporary cache view.
                        dialog.response(Gtk.ResponseType.OK)
                return False
            GLib.timeout_add(100,apply_dialog)
            window.show_settings()
            self.assertFalse(window.filters['cache'])
            self.assertEqual(Settings(settings.root).data['display_filters'],FILTER_DEFAULTS)
            window.destroy()
