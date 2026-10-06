"""GTK 3 profile highlight and shared update regression checks."""
import threading,time,unittest,json
from pathlib import Path
from unittest.mock import patch
import test_common_appearance as helpers
from test_common_appearance import pump
from saveconfig.gui import Window,Gtk,GLib
from saveconfig import VERSION
from saveconfig.settings import Settings
from saveconfig.model import PROJECT
from saveconfig.utils import atomic_json
STARTUP=Window.initial_update

class UpdateGuiTests(unittest.TestCase):
 setUp=helpers.CommonGuiTests.setUp
 tearDown=helpers.CommonGuiTests.tearDown
 def test_profile_highlight_live_changes_and_info(self):
  w=self.window;ident='1'*32
  data=dict(format_version=1,name='Privat',home=str(self.home),destination=str(self.root/'backups'),selection=[],selection_saved=False)
  atomic_json(w.profiles.folder/(ident+'.json'),data);w.apply_profile(ident);w.show_all();pump()
  self.assertIn('Privat',w.profile_label.get_text());self.assertTrue(w.profile_banner.get_style_context().has_class('active-profile'))
  self.assertGreater(w.profile_banner.get_allocated_height(),30)
  for dark in (False,True):
   Gtk.Settings.get_default().set_property('gtk-application-prefer-dark-theme',dark);pump(.2)
   w.profile_banner.get_style_context().remove_class('active-profile');pump(.2)
   x,y=w.profile_banner.translate_coordinates(w,2,2)
   image=helpers.Gdk.pixbuf_get_from_window(w.get_window(),x,y,1,1)
   plain=bytes(image.get_pixels())[:3]
   w.profile_banner.get_style_context().add_class('active-profile');pump(.2)
   image=helpers.Gdk.pixbuf_get_from_window(w.get_window(),x,y,1,1)
   active=bytes(image.get_pixels())[:3]
   self.assertNotEqual(plain,active,(dark,plain,active))
  w.destination.set_text(str(self.root/'changed'));self.assertIn(w.t('unsaved_changes'),w.profile_label.get_text())
  info=w.show_info();end=time.monotonic()+8
  while not hasattr(info,'tool_results') and time.monotonic()<end:pump(.05)
  names={t['name'] for t in info.tool_results};self.assertIn('dpkg-query',names);self.assertNotIn('tidy',names)
  w.settings.data['language']='en';w.translate();self.assertEqual(info.get_title(),'Info');self.assertTrue(w.profile_label.get_text().startswith('Active profile'))
  info.destroy();self.assertIsNone(w.info_window)
  w.destroy()
  with patch.object(Window,'initial_update',lambda *_:False):
   self.window=Window(Settings(self.settings.root),w.db,self.window.logger)
   self.window.message=lambda *_:True
   self.assertIn('Privat',self.window.profile_label.get_text())
 def test_startup_always_and_settings_hidden_sources(self):
  w=self.window
  with patch.dict(PROJECT,update_url='https://raw.githubusercontent.com/example/saveconfig/main/github/version.json'), patch('saveconfig.updates.release_info',return_value={'version':VERSION,'deb':None}) as fetch:
   STARTUP(w);pump(.3)
  fetch.assert_called_once_with('https://raw.githubusercontent.com/example/saveconfig/main/github/version.json');self.assertEqual(w.update_status_key,'software_current')
  def inspect():
   d=next(x for x in Gtk.Window.list_toplevels() if x.get_name()=='saveconfig-settings');c=d.settings_controls
   self.assertNotIn('source',c);self.assertNotIn('update_url',c);self.assertFalse(c['download'].get_sensitive())
   w.update_info={'version':'99.0.0','deb':{'url':'test'}};w.update_status_key='software_update';w.refresh_updates()
   self.assertTrue(c['download'].get_sensitive());self.assertEqual(c['update_status'].get_text(),w.t('software_update'))
   d.response(Gtk.ResponseType.CANCEL);return False
  GLib.timeout_add(100,inspect);w.show_settings()
  self.assertEqual(w.settings_dialogs,[])
  with patch.dict(PROJECT,update_url='https://raw.githubusercontent.com/example/saveconfig/main/github/version.json'), patch('saveconfig.updates.release_info',side_effect=ValueError('invalid')):w.check_update();pump(.3)
  self.assertEqual(w.update_status_key,'software_check_failed')
 def test_update_download_cancel_and_double_start(self):
  w=self.window;w.update_info={'version':'99.0.0','deb':{'url':'test'}}
  def task(info,context):
   context.progress(1,2)
   while True:context.check_cancel();time.sleep(.02)
  with patch('saveconfig.updates.download_update',side_effect=task) as fetch:
   w.download_available();pump(.25);first=w.progress_dialog
   w.download_available();self.assertIs(w.progress_dialog,first);fetch.assert_called_once()
   self.assertAlmostEqual(w.progress.get_fraction(),.5)
   w.cancel();end=time.monotonic()+3
   while w.operation and time.monotonic()<end:pump(.03)
   self.assertIsNone(w.operation);self.assertIsNone(w.progress_dialog)
