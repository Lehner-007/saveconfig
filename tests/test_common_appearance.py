"""Gemeinsame Darstellung und sichere Zustandsübergänge mit isolierten Daten."""
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from saveconfig.settings import Settings
from saveconfig.database import Database
from saveconfig.logging_setup import setup
from saveconfig.gui import Window,Gtk,GLib,Gdk
from saveconfig.models import Entry
from saveconfig.languages import Languages,download_version,github_json
from saveconfig.presentation import reachable_bounds

ROOT=Path(__file__).resolve().parents[1]


def pump(seconds=.2):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        GLib.MainContext.default().iteration(False)
        time.sleep(.005)


class CommonDataTests(unittest.TestCase):
    def test_old_settings_preserved_and_interval_validated(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as temp:
            s=Settings(Path(temp));s.file.parent.mkdir(parents=True)
            s.file.write_text(json.dumps(dict(config_version=1,geometry='900x650',language='en',github_source='https://example.invalid',active_profile='keep',update_interval_value=0,update_interval_unit='wrong')))
            loaded=Settings(Path(temp))
            self.assertEqual(loaded.data['config_version'],2)
            self.assertEqual(loaded.data['geometry'],'900x650')
            self.assertEqual(loaded.data['active_profile'],'keep')
            self.assertEqual(loaded.data['github_source'], 'https://raw.githubusercontent.com/Lehner-007/saveconfig/main/github/sprachpakete')
            self.assertFalse(loaded.data['update_check'])
            self.assertEqual(loaded.data['update_interval_value'],1)
            self.assertEqual(loaded.data['update_interval_unit'],'weeks')

    def test_missing_monitor_and_negative_origin(self):
        rect=reachable_bounds((2200,100,1180,720),[(0,0,1280,800)])
        self.assertGreaterEqual(rect[0],0);self.assertLessEqual(rect[0]+rect[2],1280)
        self.assertLessEqual(rect[1]+rect[3],800)
        rect=reachable_bounds((-1100,20,900,600),[(-1280,0,1280,800),(0,0,1920,1080)])
        self.assertLess(rect[0],0)

    def test_version_identity_schema_and_no_request_for_placeholder(self):
        with patch('saveconfig.languages.github_json',return_value={'program_id':'saveconfig','version':'0.3.0'}):
            self.assertEqual(download_version('url'),'0.3.0')
        for data in ({'program_id':'checkweb','version':'0.3.0'},{'program_id':'saveconfig','version':'v0.3.0'},[]):
            with patch('saveconfig.languages.github_json',return_value=data),self.assertRaises(ValueError):download_version('url')
        with patch('saveconfig.languages.urlopen') as opening:
            with self.assertRaises(ValueError):github_json('https://raw.githubusercontent.com/Lehner-007/xxxx/main/github/version.json')
            opening.assert_not_called()

    def test_log_sessions_preserved_and_language_at_start(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as temp:
            s=Settings(Path(temp));logger=setup(s.root);logger.info('keep')
            path=s.root/'.local/state/saveconfig/logs/saveconfig.log';before=path.read_text()
            s.data['language']='en';s.save();setup(s.root)
            text=path.read_text()
            self.assertTrue(text.startswith(before))
            self.assertEqual(text.count('='*72),4)
            self.assertIn('Application started',text)
            self.assertRegex(text,r'\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}:\d{2}')


@unittest.skipUnless(Gtk.init_check()[0],'No graphical display')
class CommonGuiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'work')
        self.root=Path(self.tmp.name);self.home=self.root/'home';self.home.mkdir()
        self.settings=Settings(self.root/'state');self.settings.data['home']=str(self.home)
        self.window=Window(self.settings,Database(self.settings.db_path),setup(self.settings.root))
        self.window.message=lambda *_,**kwargs:True
        self.theme=Gtk.Settings.get_default()
        self.previous_dark=self.theme.get_property('gtk-application-prefer-dark-theme')
        pump()

    def tearDown(self):
        self.theme.set_property('gtk-application-prefer-dark-theme',self.previous_dark)
        self.window.destroy();pump(.05);self.tmp.cleanup()

    def test_about_image_and_progress_stays_same_size_for_long_text(self):
        w=self.window
        about=w.about();pump()
        logo=about.get_logo()
        self.assertLessEqual(max(logo.get_width(),logo.get_height()),128)
        about.destroy()
        w.operation_cancellable=True
        w.show_progress('scan');pump(.4)
        initial=w.progress_dialog.get_size()
        context=w.progress_label.get_pango_context()
        metrics=context.get_metrics(context.get_font_description(),context.get_language())
        from gi.repository import Pango
        line_height=(metrics.get_ascent()+metrics.get_descent()+Pango.SCALE-1)//Pango.SCALE
        self.assertGreaterEqual(w.progress_text_scroll.get_allocated_height(),4*line_height)
        for text in ('Kurz','Zeile 1\nZeile 2\nZeile 3','/sehr_langer_pfad'*100,'\n'.join(['Lange Ausgabe']*20)):
            w.progress_label.set_text(text);pump(.2)
            self.assertEqual(w.progress_dialog.get_size(),initial)
            self.assertEqual(w.progress_label.get_text(),text)
        w.progress_dialog.destroy();w.progress_dialog=None

    def test_log_view_readonly_and_refresh(self):
        w=self.window;w.logger.info('First operation')
        dialog=w.show_log();pump()
        view=dialog.log_controls['view'];buffer=view.get_buffer()
        text=buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),True)
        self.assertIn('First operation',text);self.assertIn('='*72,text)
        self.assertFalse(view.get_editable())
        w.logger.info('Second operation');dialog.log_controls['reload'].clicked();pump()
        text=buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),True)
        self.assertIn('Second operation',text)
        dialog.destroy()

    def test_profile_manager_apply_cancel_and_restart(self):
        w=self.window
        item=dict(format_version=1,name='Labor VM',home=str(self.home),destination=str(self.root/'backup'),selection=['~/.ssh'],selection_saved=True)
        key=w.profiles.save(item)
        dialog=w.show_profiles();pump()
        controls=dialog.profile_controls
        row=next(r for r in controls['list'].get_children() if r.profile_id==key)
        controls['list'].select_row(row);pump()
        self.assertEqual(controls['fields']['name'].get_text(),'Labor VM')
        self.assertEqual(controls['fields']['home'].get_text(),str(self.home))
        controls['fields']['name'].set_text('Verworfen')
        dialog.response(Gtk.ResponseType.CANCEL);pump()
        self.assertEqual(w.profiles.get(key)['name'],'Labor VM')
        dialog=w.show_profiles();controls=dialog.profile_controls
        controls['list'].select_row(next(r for r in controls['list'].get_children() if r.profile_id==key))
        controls['fields']['name'].set_text('Meine VM')
        dialog.response(Gtk.ResponseType.OK);pump()
        self.assertEqual(w.settings.data['active_profile'],key)
        self.assertTrue(w.profile_label.get_visible())
        self.assertIn('Meine VM',w.profile_label.get_text())
        self.assertIn('Meine VM',w.get_title())
        self.assertEqual(w.profile_selection,{'~/.ssh'})
        reloaded=Window(Settings(w.settings.root),Database(w.settings.db_path),w.logger)
        self.assertIn('Meine VM',reloaded.profile_label.get_text())
        self.assertEqual(reloaded.profile_selection,{'~/.ssh'})
        reloaded.destroy()

    def test_menu_separators_and_actual_row_colors_light_dark(self):
        w=self.window
        self.assertEqual(sum(key=='settings' for _,key in w.menu_labels),1)
        file_menu=w.menu_bar.get_children()[0].get_submenu()
        keys=[key for widget,key in w.menu_labels if widget in file_menu.get_children()]
        self.assertEqual(keys[-3:],['profiles','settings','quit'])
        w.entries=[Entry('First','~/a',exists=True,status='found',category='program'),Entry('Second','~/b',exists=True,status='found',category='program')]
        for dark in (False,True):
            self.theme.set_property('gtk-application-prefer-dark-theme',dark)
            for code in ('de','en'):
                w.settings.data['language']=code;w.translate();pump()
                file_menu.popup_at_widget(w.menu_bar,Gdk.Gravity.SOUTH_WEST,Gdk.Gravity.NORTH_WEST,None);pump()
                separators=[child for child in file_menu.get_children() if isinstance(child,Gtk.SeparatorMenuItem)]
                self.assertEqual(len(separators),3)
                self.assertTrue(all(s.get_mapped() and s.get_allocated_width()>20 and s.get_allocated_height()>=1 for s in separators))
                file_menu.popdown();pump()
                single=Gtk.Menu();single.append(Gtk.MenuItem(label=w.t('settings')));single.show_all()
                single.popup_at_widget(w.menu_bar,Gdk.Gravity.SOUTH_WEST,Gdk.Gravity.NORTH_WEST,None);pump()
                self.assertLessEqual(single.get_allocated_height(),single.get_preferred_height().natural_height+2)
                single.popdown();single.destroy();pump()
            w.view.get_selection().unselect_all();w.view._stripe_hover=None;w.view.queue_draw();pump()
            image=Gdk.pixbuf_get_from_window(w.view.get_bin_window(),0,0,w.view.get_allocated_width(),100)
            areas=[w.view.get_background_area(Gtk.TreePath.new_from_indices([i]),w.columns[1][0]) for i in (0,1)]
            pixels=image.get_pixels();stride=image.get_rowstride();channels=image.get_n_channels()
            scale=w.view.get_scale_factor()
            positions=[((a.x+2)*scale,(a.y+a.height//2)*scale) for a in areas]
            colors=[tuple(pixels[y*stride+x*channels:y*stride+x*channels+3]) for x,y in positions]
            self.assertNotEqual(colors[0],colors[1],(dark,colors))

    def test_settings_order_cancel_and_typed_save(self):
        w=self.window;before=dict(w.settings.data)
        def cancel():
            dialog=next(x for x in Gtk.Window.list_toplevels() if x.get_name()=='saveconfig-settings')
            c=dialog.settings_controls
            c['fields']['home'].set_text('/does-not-exist');c['count'].set_value(8)
            labels=[]
            def collect(widget):
                if isinstance(widget,Gtk.Label):labels.append(widget.get_text())
                if isinstance(widget,Gtk.Container):
                    for child in widget.get_children():collect(child)
            collect(dialog.get_content_area())
            self.assertLess(labels.index(w.t('source_settings')),labels.index(w.t('update_settings')))
            self.assertLess(labels.index(w.t('update_settings')),labels.index(w.t('language_extensions')))
            self.assertLess(labels.index(w.t('language_extensions')),labels.index(w.t('language')))
            dialog.response(Gtk.ResponseType.CANCEL);return False
        GLib.timeout_add(100,cancel);w.show_settings();self.assertEqual(w.settings.data,before)
        def save():
            dialog=next(x for x in Gtk.Window.list_toplevels() if x.get_name()=='saveconfig-settings')
            c=dialog.settings_controls;c['language'].set_active_id('en');c['count'].set_text('7');c['units'].set_active_id('months')
            dialog.response(Gtk.ResponseType.OK);return False
        GLib.timeout_add(100,save);w.show_settings()
        self.assertEqual(w.settings.data['language'],'en')
        self.assertEqual(w.settings.data['update_interval_value'],7)
        self.assertEqual(w.settings.data['update_interval_unit'],'months')

    def test_progress_centering_double_start_cancel_and_close_wait(self):
        w=self.window;calls=[]
        def work(op):
            while not op.cancel.wait(.02):op.callback('Current file')
            op.check()
        w.start(work,lambda result:calls.append(result),title_key='scan');pump(.4)
        dialog=w.progress_dialog
        self.assertTrue(dialog.get_modal());self.assertIs(dialog.get_transient_for(),w)
        parent=w.get_window().get_frame_extents();child=dialog.get_window().get_frame_extents()
        self.assertLessEqual(abs(parent.x+parent.width/2-child.x-child.width/2),3)
        self.assertLessEqual(abs(parent.y+parent.height/2-child.y-child.height/2),3)
        self.assertEqual(w.progress_label.get_text(),'Current file')
        w.start(lambda op:calls.append('double'),lambda _:None)
        w.cancel();self.assertFalse(w.progress_cancel.get_sensitive())
        deadline=time.monotonic()+3
        while w.operation and time.monotonic()<deadline:pump(.02)
        self.assertIsNone(w.operation);self.assertIsNone(w.progress_dialog);self.assertEqual(calls,[])
        w.start(work,lambda _:None);pump(.1);w.close()
        self.assertTrue(w.closing)
        while w.operation and time.monotonic()<deadline:pump(.02)
        self.assertFalse(w.alive)

    def test_progress_close_immediate_and_safe(self):
        from saveconfig.models import Operation
        w=self.window
        w.operation=Operation();w.operation_cancellable=True
        w.show_progress('working')
        dialog=w.progress_dialog
        self.assertTrue(w.close_progress(dialog))
        self.assertTrue(w.operation.cancel.is_set())
        self.assertIsNone(w.progress_dialog)
        self.assertIsNotNone(w.operation)
        w.operation=None
        w.destroy()

    def test_version_check_and_failure_leave_working_app(self):
        w=self.window
        with patch.dict(__import__('saveconfig.model',fromlist=['PROJECT']).PROJECT,update_url='https://raw.githubusercontent.com/example/saveconfig/main/github/version.json'), patch('saveconfig.updates.release_info',return_value={'version':'0.5.0','deb':None}):
            w.check_update('https://example.invalid');pump(.4)
        self.assertTrue(w.settings.data['last_update_check'])
        self.assertIsNone(w.progress_dialog)
        with patch.dict(__import__('saveconfig.model',fromlist=['PROJECT']).PROJECT,update_url='https://raw.githubusercontent.com/example/saveconfig/main/github/version.json'), patch('saveconfig.updates.release_info',side_effect=ValueError('invalid_version')):
            w.check_update('https://example.invalid');pump(.4)
        self.assertIsNone(w.progress_dialog);self.assertTrue(w.alive)

    def test_live_language_save_rtl_and_selection_preserved(self):
        w=self.window
        for code,name in (('ar','Arabic test fixture'),('fr','French test fixture')):
            pack=json.loads((ROOT/'lang/en.json').read_text())
            pack.update(code=code,name=name,help_html='<html><body><h1>Offline help</h1></body></html>')
            w.lang.install(pack)
        w.entries=[Entry('A','~/a',exists=True,selected=True,status='found',category='program'),
                   Entry('B','~/b',exists=True,status='found',category='program')]
        w.scan_home=str(self.home);w.refresh();w.view.get_selection().select_path(Gtk.TreePath.new_from_indices([1]))
        w.profile_selection={'~/a'}
        for code in ('en','ar','fr','de'):
            def save(code=code):
                dialog=next(x for x in Gtk.Window.list_toplevels() if x.get_name()=='saveconfig-settings')
                dialog.settings_controls['language'].set_active_id(code);dialog.response(Gtk.ResponseType.OK);return False
            GLib.timeout_add(80,save);w.show_settings()
            self.assertEqual(w.settings.data['language'],code)
            self.assertEqual(w.get_direction(),Gtk.TextDirection.RTL if code=='ar' else Gtk.TextDirection.LTR)
            self.assertEqual(w.home.get_direction(),Gtk.TextDirection.LTR)
            self.assertEqual([e.selected for e in w.entries],[True,False])
            model,iterator=w.view.get_selection().get_selected();self.assertEqual(model[iterator][8],1)
            self.assertEqual(w.profile_selection,{'~/a'})
            self.assertEqual(w.home.get_text(),str(self.home))


if __name__=='__main__':unittest.main()
