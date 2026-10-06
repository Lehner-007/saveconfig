import unittest
import tempfile
from pathlib import Path
from saveconfig.settings import Settings
from saveconfig.profiles import Profiles
from saveconfig.database import Database
from saveconfig.gui import Window, Gtk, GLib
from saveconfig.logging_setup import setup

ROOT = Path(__file__).resolve().parent.parent

class ProfileTests(unittest.TestCase):
    def test_persistence_import_conflicts_and_validation(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as temp:
            root = Path(temp)
            settings = Settings(root / 'state')
            profiles = Profiles(settings)
            data = dict(format_version=1, name='VM', home=str(root / 'vm'), destination=str(root / 'backup'), selection=['~/.ssh'], selection_saved=True)
            ident = profiles.save(data)
            self.assertEqual(Profiles(settings).get(ident), data)
            with self.assertRaises(ValueError):
                profiles.save(dict(data, name='vm'))
            target = root / 'export.json'
            profiles.export(ident, target)
            with self.assertRaises(ValueError):
                profiles.export(ident, target)
            other = Profiles(Settings(root / 'other'))
            self.assertEqual(other.get(other.import_file(target)), data)
            for bad in [dict(data, home='../outside'), dict(data, selection='bad'), dict(data, format_version=9)]:
                with self.assertRaises(ValueError):
                    profiles.save(bad)
            with self.assertRaises(ValueError):
                profiles.get('../outside')
            self.assertEqual(settings.data['language'], 'de')

    def test_smb_profile_export_import_offline(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as temp:
            root=Path(temp);profiles=Profiles(Settings(root/'state'))
            data=dict(format_version=1,name='OMV',home=str(root),destination='',selection=[],selection_saved=False,smb_server='omv',smb_share='Sicherungen')
            ident=profiles.save(data)
            exported=root/'profile.json';profiles.export(ident,exported)
            other=Profiles(Settings(root/'other'))
            self.assertEqual(other.get(other.import_file(exported)),data)
            with self.assertRaises(ValueError):profiles.validate(dict(data,smb_share='../unsafe'))

    @unittest.skipUnless(Gtk.init_check()[0], 'No display')
    def test_gui_switch_and_dialogs(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as temp:
            root = Path(temp)
            home = root / 'vm'
            (home / '.config/filezilla').mkdir(parents=True)
            (home / '.config/filezilla/x').write_text('sample')
            pc = root / 'pc'
            pc.mkdir()
            settings = Settings(root / 'state')
            settings.data['home'] = str(home)
            window = Window(settings, Database(settings.db_path), setup(settings.root))
            ident = window.profiles.save(dict(format_version=1,name='PC',home=str(pc),destination=str(root/'backup'),selection=['~/.ssh'],selection_saved=True,smb_server='omv',smb_share='backup'))
            window.entries = [object()]
            window.apply_profile(ident)
            self.assertEqual(window.home.get_text(), str(pc))
            self.assertEqual(window.entries, [])
            self.assertEqual(settings.data['smb_server'],'omv')
            self.assertEqual(settings.data['smb_share'],'backup')
            self.assertEqual(window.profile_selection, {'~/.ssh'})
            self.assertIn('PC', window.profile_label.get_text())
            self.assertIn('PC', window.get_title())
            self.assertNotIn('ungespeicherte Änderungen', window.profile_label.get_text())
            window.destination.set_text(str(root/'changed'))
            self.assertIn('ungespeicherte Änderungen', window.profile_label.get_text())
            window.destination.set_text(str(root/'backup'))
            self.assertNotIn('ungespeicherte Änderungen', window.profile_label.get_text())
            self.assertEqual(window.watermark.get_parent(), window.output_overlay)
            self.assertTrue(window.output_overlay.get_overlay_pass_through(window.watermark))
            self.assertAlmostEqual(window.watermark.get_opacity(), .10, places=2)
            about = window.about()
            self.assertEqual(about.get_program_name(), 'saveconfig')
            self.assertIsNotNone(about.get_logo())
            about.destroy()
            def cancel_dialog():
                for item in Gtk.Window.list_toplevels():
                    if isinstance(item, Gtk.Dialog):
                        item.response(Gtk.ResponseType.CANCEL)
                return False
            GLib.timeout_add(100, cancel_dialog)
            before = dict(settings.data)
            window.show_settings()
            self.assertEqual(settings.data, before)
            window.destroy()
