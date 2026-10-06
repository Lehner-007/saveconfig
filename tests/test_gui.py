import unittest
import tempfile
import time
import json
from pathlib import Path
from unittest.mock import patch
from saveconfig.settings import Settings
from saveconfig.database import Database
from saveconfig.logging_setup import setup
from saveconfig.gui import Window, Gtk, GLib, Gdk
from saveconfig.verify import verify
from saveconfig.models import Operation

ROOT = Path(__file__).resolve().parent.parent

@unittest.skipUnless(Gtk.init_check()[0], 'No graphical display')
class GuiTests(unittest.TestCase):
    def test_gui_scan_backup_translation_cancel_and_layout(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as folder:
            root = Path(folder)
            home = root / 'home'
            (home / '.config/filezilla').mkdir(parents=True)
            (home / '.config/filezilla/a.xml').write_text('<sample/>')
            settings = Settings(root / 'state')
            settings.data.update(home=str(home), destination=str(root / 'backups'))
            window = Window(settings, Database(settings.db_path), setup(settings.root))
            messages = []
            window.message = lambda key, detail='', question=False: messages.append((key, detail)) or True
            def pump():
                deadline = time.monotonic() + 15
                while window.operation is not None and time.monotonic() < deadline:
                    GLib.MainContext.default().iteration(False)
                    time.sleep(.01)
                for _ in range(20):
                    GLib.MainContext.default().iteration(False)
                self.assertIsNone(window.operation)
            window.scan()
            pump()
            self.assertTrue(any(e.path == '~/.config/filezilla' and e.exists for e in window.entries))
            from saveconfig.classification import visible
            self.assertEqual(len(window.model), sum(visible(e, window.filters) for e in window.entries))
            window.settings.data['language'] = 'en'
            window.translate()
            self.assertEqual(window.columns[1][0].get_title(), 'Program')
            selected = {e.path for e in window.entries if e.selected}
            window.settings.data['language'] = 'de'
            window.translate()
            self.assertEqual(selected, {e.path for e in window.entries if e.selected})
            with patch('saveconfig.backup.inventory', return_value={'installed': [], 'manual': [], 'automatic': []}):
                window.backup()
                pump()
            self.assertIsNotNone(window.last_backup)
            self.assertEqual(verify(window.last_backup, Operation()), [])
            window.select(False)
            self.assertFalse(any(e.selected for e in window.entries))
            window.select(True)
            self.assertTrue(next(e for e in window.entries if e.exists).selected)
            window.resize(800, 600)
            for _ in range(100):
                GLib.MainContext.default().iteration(False)
                time.sleep(.01)
            native = window.get_window()
            shot = Gdk.pixbuf_get_from_window(native, 0, 0, window.get_allocated_width(), window.get_allocated_height())
            shot.savev(str(ROOT / 'work/gui-small.png'), 'png', [], [])
            window.settings.data['language'] = 'en'
            Gtk.Settings.get_default().set_property('gtk-application-prefer-dark-theme', True)
            window.translate()
            for _ in range(100):
                GLib.MainContext.default().iteration(False)
                time.sleep(.01)
            shot = Gdk.pixbuf_get_from_window(native, 0, 0, window.get_allocated_width(), window.get_allocated_height())
            shot.savev(str(ROOT / 'work/gui-dark-en.png'), 'png', [], [])
            window.start(lambda op: (time.sleep(.05), op.check()), lambda result: None)
            window.cancel()
            pump()
            self.assertEqual(window.status_key, 'cancelled')
            window.save_settings()
            self.assertTrue(settings.file.exists())
            window.destroy()
            # Do not emit Gtk.main_quit when no Gtk.main loop is active.

if __name__ == '__main__':
    unittest.main()
