import json
import threading
import webbrowser
from urllib.error import URLError
from pathlib import Path
from datetime import datetime,timezone,timedelta
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, GdkPixbuf, Gdk, GObject, Pango
from . import VERSION, AUTHOR
from .models import Operation, Cancelled
from .profiles import Profiles
from .model import PROJECT
from .classification import FILTER_DEFAULTS, visible, excluded_backup
from .scanner import scan
from .backup import backup
from .verify import verify, load_manifest
from .restore import preview
from .languages import Languages, ROOT
from .utils import atomic_json, source_path
from .presentation import style_menus,striped_rows,reachable_bounds,monitor_rects,center_after_map

class Window(Gtk.Window):
    def __init__(self, settings, db, logger):
        super().__init__(title=f'saveconfig {VERSION}')
        self.settings, self.db, self.logger = settings, db, logger
        self.lang = Languages(settings)
        self.profiles = Profiles(settings)
        self.profile_selection = None
        if settings.data['active_profile']:
            try:
                saved=self.profiles.get(settings.data['active_profile'])
                for key in ('smb_server','smb_share','target_kind','mount_point','mount_source'):settings.data[key]=saved.get(key,'local' if key=='target_kind' else '')
                self.profile_selection=set(saved['selection']) if saved['selection_saved'] else None
            except (OSError,ValueError):pass
        self.scan_home = None
        provider = Gtk.CssProvider()
        provider.load_from_data(b"* { font-weight: normal; }")
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.entries = []
        self.operation = None
        self.progress_dialog=None
        self.closing=False
        self.alive=True
        self.last_backup = None
        self.update_info=None
        self.update_status_key="software_checking"
        self.update_check_running=False
        self.settings_dialogs=[]
        self.info_window=None
        self.labels = []
        self.buttons = []
        self.menu_labels = []
        self.action_items = []
        self.model = Gtk.ListStore(bool, str, str, GObject.TYPE_INT64, GObject.TYPE_INT64, str, str, str, int)
        self.view = Gtk.TreeView(model=self.model)
        self.view.connect('button-press-event', self.context_menu)
        self.set_default_size(1180, 720)
        try:
            width, height = map(int, settings.data['geometry'].split('x'))
            self.normal_rect=reachable_bounds((settings.data['window_x'],settings.data['window_y'],width,height),monitor_rects())
            self.resize(*self.normal_rect[2:])
            if settings.data['window_position_known']:self.move(*self.normal_rect[:2])
            if settings.data['window_maximized']:self.maximize()
            self.set_icon_from_file(str(ROOT / 'resources/icon.png'))
        except (ValueError, GLib.Error):
            pass
        self.connect('delete-event', self.close)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add(outer)
        accelerators = Gtk.AccelGroup()
        self.add_accel_group(accelerators)
        bar = Gtk.MenuBar()
        self.menu_bar=bar
        self.menu_provider=style_menus(bar)
        outer.pack_start(bar, False, False, 0)
        definitions = [
            ('file', [('scan', self.scan), ('backup', self.backup), ('backups', self.show_backups), ('verify', self.verify), ('restore', self.restore), ('cancel', self.cancel),None,('profiles',self.show_profiles),None,('settings',self.show_settings),None,('quit', self.close)]),
            ('catalog', [('learn', self.learn), ('all', lambda *_: self.select(True)), ('none', lambda *_: self.select(False))]),
            ('help', [('help', self.help), ('log',self.show_log), ('info',self.show_info), ('about', self.about)])]
        for title, children in definitions:
            item = Gtk.MenuItem()
            self.menu_labels.append((item, title))
            submenu = Gtk.Menu()
            submenu.get_style_context().add_class('saveconfig-menu')
            item.set_submenu(submenu)
            bar.append(item)
            for entry in children:
                if entry is None:
                    submenu.append(Gtk.SeparatorMenuItem());continue
                key,callback=entry
                child = Gtk.ImageMenuItem() if key=="info" else Gtk.MenuItem()
                if key=="info":
                    child.set_image(Gtk.Image.new_from_icon_name("dialog-information-symbolic",Gtk.IconSize.MENU))
                    child.set_always_show_image(True)
                self.menu_labels.append((child, key))
                child.connect('activate', callback)
                submenu.append(child)
                shortcut = {'scan': '<Control>f', 'backup': '<Control>s', 'backups': '<Control>b', 'verify': '<Control>v', 'restore': '<Control>r', 'quit': '<Control>q', 'cancel': 'Escape', 'help': 'F1'}.get(key)
                if shortcut:
                    accel_key, mods = Gtk.accelerator_parse(shortcut)
                    child.add_accelerator('activate', accelerators, accel_key, mods, Gtk.AccelFlags.VISIBLE)
                if key in ('scan', 'backup', 'backups', 'verify', 'restore', 'learn', 'all', 'none', 'install_languages', 'settings', 'profiles', 'save_profile', 'load_profile', 'import_profile', 'export_profile'):
                    self.action_items.append(child)
                if key == 'cancel':
                    self.cancel_item = child
        grid = Gtk.Grid(column_spacing=8, row_spacing=8, margin=12)
        outer.pack_start(grid, False, False, 0)
        self.home = Gtk.Entry(text=settings.data['home'], hexpand=True, width_chars=12)
        self.destination = Gtk.Entry(text=settings.data['destination'], hexpand=True, width_chars=12)
        self.home.set_direction(Gtk.TextDirection.LTR);self.destination.set_direction(Gtk.TextDirection.LTR)
        for row, (key, entry) in enumerate([('home', self.home), ('destination', self.destination)]):
            label = Gtk.Label(xalign=0)
            self.labels.append((label, key))
            grid.attach(label, 0, row, 1, 1)
            grid.attach(entry, 1, row, 1, 1)
            button = Gtk.Button()
            self.buttons.append((button, 'browse'))
            button.connect('clicked', lambda _, field=entry: self.choose(field))
            grid.attach(button, 2, row, 1, 1)
        smb_button=Gtk.Button()
        self.buttons.append((smb_button,'smb_destination'))
        smb_button.connect('clicked',self.show_smb)
        grid.attach(smb_button,3,1,1,1)
        self.profile_label = Gtk.Label(xalign=0, margin_start=12,margin_end=12,wrap=True)
        self.profile_banner=Gtk.Box(spacing=10,margin_start=12,margin_end=12)
        self.profile_banner.get_style_context().add_class('profile-banner')
        self.profile_icon=Gtk.Image.new_from_icon_name('emblem-default-symbolic',Gtk.IconSize.LARGE_TOOLBAR)
        self.profile_banner.pack_start(self.profile_icon,False,False,0)
        self.profile_banner.pack_start(self.profile_label,True,True,0)
        profile_style=Gtk.CssProvider()
        profile_style.load_from_data(b'.profile-banner {padding: 10px; border: 1px solid alpha(@theme_fg_color,0.20); border-radius: 4px;} .profile-banner.active-profile {background-color: alpha(@theme_selected_bg_color,0.16); border-left: 4px solid @theme_selected_bg_color;}')
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),profile_style,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.profile_style=profile_style
        outer.pack_start(self.profile_banner,False,False,0)
        hint = Gtk.Label(xalign=0, margin_start=12, margin_end=12, wrap=True, max_width_chars=65)
        self.labels.append((hint, 'sensitive_hint'))
        outer.pack_start(hint, False, False, 0)
        filter_box = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, column_spacing=10, row_spacing=4, min_children_per_line=1, max_children_per_line=6, margin_start=12, margin_end=12)
        label = Gtk.Label()
        self.labels.append((label, 'display'))
        filter_box.add(label)
        self.filters = dict(settings.data['display_filters'])
        self.filter_widgets = {}
        for key in FILTER_DEFAULTS:
            if key=='cache':continue
            button = Gtk.CheckButton()
            button.set_active(self.filters[key])
            self.labels.append((button, 'filter_' + key))
            self.filter_widgets[key] = button
            button.connect('toggled', self.filter_changed, key)
            filter_box.add(button)
        outer.pack_start(filter_box, False, False, 0)
        toggle = Gtk.CellRendererToggle()
        toggle.connect('toggled', self.toggle)
        col = Gtk.TreeViewColumn('', toggle, active=0)
        self.view.append_column(col)
        self.columns = [(col, 'selected')]
        for index, key in enumerate(['program', 'path', 'size', 'files', 'kind', 'status', 'sensitive'], 1):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn('', renderer, text=index)
            column.set_resizable(True)
            column.set_sort_column_id(index)
            self.view.append_column(column)
            self.columns.append((column, key))
        striped_rows(self.view)
        scroll = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        scroll.add(self.view)
        self.output_overlay = Gtk.Overlay()
        self.output_overlay.add(scroll)
        self.watermark = Gtk.Image(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        self.watermark.set_opacity(0.10)
        self.output_overlay.add_overlay(self.watermark)
        self.output_overlay.set_overlay_pass_through(self.watermark, True)
        self.watermark_source = None
        try:
            self.watermark_source = GdkPixbuf.Pixbuf.new_from_file(str(ROOT / 'resources/icon.png'))
        except GLib.Error:
            pass
        self.output_overlay.connect('size-allocate', self.resize_watermark)
        outer.pack_start(self.output_overlay, True, True, 0)
        footer = Gtk.Box(spacing=8, margin=8)
        self.status = Gtk.Label(xalign=0, hexpand=True)
        footer.pack_start(self.status, True, True, 0)
        outer.pack_start(footer, False, False, 0)
        self.status_key = 'ready'
        self.translate()
        self.cancel_item.set_sensitive(False)
        self.connect('configure-event',self.remember_geometry)
        self.screen_handler=self.get_screen().connect('monitors-changed',self.monitors_changed)
        self.connect('destroy',self.on_destroy)
        self.show_all()
        self.home.connect('changed', lambda *_: self.update_profile_label())
        self.destination.connect('changed', lambda *_: self.update_profile_label())
        if settings.data['active_profile']:
            try:
                profile = self.profiles.get(settings.data['active_profile'])
                self.profile_selection = set(profile['selection']) if profile['selection_saved'] else None
            except (OSError, ValueError):
                pass
        if settings.warning:
            self.message('settings_damaged')
        GLib.idle_add(self.initial_update)
        self.update_timer=GLib.timeout_add_seconds(60,self.periodic_update)

    def periodic_update(self):
        self.auto_update()
        return self.alive

    def remember_geometry(self,*_):
        state=self.get_window().get_state() if self.get_window() else 0
        if not self.is_maximized() and not state&Gdk.WindowState.FULLSCREEN:
            self.normal_rect=(*self.get_position(),*self.get_size())
        return False

    def monitors_changed(self,*_):
        if not self.alive:return
        self.normal_rect=reachable_bounds(self.normal_rect,monitor_rects())
        if not self.is_maximized():
            self.resize(*self.normal_rect[2:]);self.move(*self.normal_rect[:2])

    def on_destroy(self,*_):
        self.alive=False
        GLib.source_remove(self.update_timer)
        self.get_screen().disconnect(self.screen_handler)
        if self.progress_dialog:self.progress_dialog.destroy();self.progress_dialog=None
        if self.info_window:self.info_window.destroy()
        for dialog in self.settings_dialogs[:]:dialog.destroy()
        if Gtk.main_level():Gtk.main_quit()

    def resize_watermark(self, widget, allocation):
        if self.watermark_source is None:
            return
        size = max(32, min(320, int(min(allocation.width, allocation.height) * .65)))
        if getattr(self, '_watermark_size', None) == size:
            return
        self._watermark_size = size
        source = self.watermark_source
        ratio = min(size / source.get_width(), size / source.get_height())
        self.watermark.set_from_pixbuf(source.scale_simple(max(1, int(source.get_width() * ratio)), max(1, int(source.get_height() * ratio)), GdkPixbuf.InterpType.BILINEAR))

    def t(self, key):
        return self.lang.text(key)

    def translate(self):
        for widget, key in self.labels + self.buttons + self.menu_labels:
            widget.set_label(self.t(key))
        for col, key in self.columns:
            col.set_title(self.t(key))
        self.status.set_text(self.t(self.status_key))
        direction=Gtk.TextDirection.RTL if self.settings.data['language'].split('-')[0] in ('ar','he','fa','ur') else Gtk.TextDirection.LTR
        Gtk.Widget.set_default_direction(direction);self.set_direction(direction)
        self.update_profile_label()
        if self.info_window and hasattr(self.info_window,"refresh_info"):self.info_window.refresh_info()
        self.refresh_updates()
        self.refresh()

    def refresh(self):
        model, iterator = self.view.get_selection().get_selected()
        chosen = model[iterator][8] if iterator is not None else None
        self.model.clear()
        for i, entry in enumerate(self.entries):
            if excluded_backup(entry):
                entry.selected=False
                continue
            if not visible(entry, self.filters):
                continue
            self.model.append([entry.selected, entry.program or self.t('unknown'), entry.path, entry.size, entry.files, self.t(entry.category) + ' / ' + self.t(entry.kind), self.t(entry.status), self.t('yes' if entry.sensitive else 'no'), i])
        if chosen is not None:
            for row in self.model:
                if row[8] == chosen:
                    self.view.get_selection().select_path(row.path)
                    break

    def filter_changed(self, widget, key):
        self.filters[key] = widget.get_active()
        self.refresh()

    def context_menu(self, widget, event):
        if event.button != 3 or self.operation:
            return False
        hit = self.view.get_path_at_pos(int(event.x), int(event.y))
        if not hit:
            return False
        self.view.get_selection().select_path(hit[0])
        entry = self.entries[self.model[hit[0]][8]]
        menu = Gtk.Menu()
        for category, kind in [('program', 'config'), ('system_desktop', 'config'), ('cache', 'cache'), ('program_data', 'data'), ('backup_file', 'unknown'), ('ignored', 'unknown')]:
            item = Gtk.MenuItem(label=self.t('classification_program' if category == 'program' else category))
            def classify(_, category=category, kind=kind):
                self.db.classify(entry.path, category, kind)
                entry.category, entry.kind, entry.known = category, kind, True
                entry.program = entry.program or 'Katalog'
                self.refresh()
            item.connect('activate', classify)
            menu.append(item)
        menu.show_all()
        menu.popup_at_pointer(event)
        return True

    def toggle(self, _, path):
        if self.operation:
            return
        row = self.model[path]
        e = self.entries[row[8]]
        if e.exists and e.status != 'error' and not excluded_backup(e):
            e.selected = not e.selected
            row[0] = e.selected
            self.update_profile_label()

    def select(self, selected):
        for e in self.entries:
            if e.exists and e.status != 'error' and not excluded_backup(e):
                e.selected = selected
        self.refresh()
        self.update_profile_label()

    def message(self, key, detail='', question=False):
        dialog = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION if question else Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.YES_NO if question else Gtk.ButtonsType.OK, text=self.t(key))
        if key == 'about':
            try:
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(ROOT / 'resources/icon.png'), 64, 64, True)
                dialog.set_image(Gtk.Image.new_from_pixbuf(pix))
            except GLib.Error:
                pass
        if detail:
            dialog.format_secondary_text(detail)
        result = dialog.run()
        dialog.destroy()
        return result == Gtk.ResponseType.YES

    def show_smb(self, *_):
        from .smb import share_uri, connect
        dialog=Gtk.Dialog(title=self.t('smb_destination'),transient_for=self,modal=True)
        dialog.add_buttons(self.t('cancel'),Gtk.ResponseType.CANCEL,self.t('smb_connect'),Gtk.ResponseType.OK)
        grid=Gtk.Grid(column_spacing=12,row_spacing=12,margin=16)
        dialog.get_content_area().add(grid)
        fields=[]
        for row,key in enumerate(('smb_server','smb_share')):
            entry=Gtk.Entry(text=self.settings.data[key],width_chars=30)
            grid.attach(Gtk.Label(label=self.t(key),xalign=0),0,row,1,1)
            grid.attach(entry,1,row,1,1);fields.append(entry)
        note=Gtk.Label(label=self.t('smb_hint'),wrap=True,max_width_chars=55,xalign=0)
        grid.attach(note,0,2,2,1)
        dialog.show_all();response=dialog.run()
        server,share=(entry.get_text().strip() for entry in fields)
        dialog.destroy()
        if response!=Gtk.ResponseType.OK:return
        try:uri=share_uri(server,share)
        except ValueError as exc:self.message(str(exc));return
        self.settings.data.update(smb_server=server,smb_share=share)
        self.settings.save()
        def complete(path):
            self.settings.data.update(target_kind='local',mount_point='',mount_source='')
            self.destination.set_text(str(path))
            self.save_settings();self.update_profile_label()
        self.start(lambda op:connect(uri,op,self),complete,title_key='smb_connect',save_paths=False)

    def choose(self, entry=None, title='browse'):
        dialog = Gtk.FileChooserDialog(title=self.t(title), transient_for=self, action=Gtk.FileChooserAction.SELECT_FOLDER)
        dialog.add_buttons(self.t('cancel'), Gtk.ResponseType.CANCEL, self.t('choose'), Gtk.ResponseType.OK)
        dialog.set_show_hidden(False)
        if entry and Path(entry.get_text()).is_dir():
            dialog.set_current_folder(entry.get_text())
        result = dialog.get_filename() if dialog.run() == Gtk.ResponseType.OK else None
        dialog.destroy()
        if result and entry:
            entry.set_text(result)
        return result

    def save_settings(self):
        if not Path(self.home.get_text()).is_dir():
            raise ValueError('invalid_home')
        x,y,width,height=self.normal_rect
        self.settings.data.update(home=self.home.get_text(), destination=self.destination.get_text(), geometry='%dx%d' % (width,height),
                                  window_x=x,window_y=y,window_position_known=True,window_maximized=self.is_maximized())
        self.settings.save()

    def start(self, function, finished, *, title_key='working',parent=None,save_paths=True,cancellable=True,quiet=False):
        if self.operation:
            return
        try:
            if save_paths:self.save_settings()
        except (OSError, ValueError):
            self.message('invalid_home')
            return
        self.operation = Operation()
        op = self.operation
        # Viele Dateimeldungen zusammenfassen, statt den GTK-Hauptthread zu fluten.
        op.callback=lambda message:setattr(op,'progress_target',str(message))
        self.operation_cancellable=cancellable
        self.status_key = 'working'
        self.status.set_text(self.t('working'))
        self.logger.info('%s: %s',self.t(title_key),self.t('working'))
        for item in self.action_items:
            item.set_sensitive(False)
        self.home.set_sensitive(False)
        self.destination.set_sensitive(False)
        for button, _ in self.buttons:
            button.set_sensitive(False)
        self.cancel_item.set_sensitive(cancellable)
        self.refresh_updates()
        if not quiet:self.show_progress(title_key,parent)
        timer = GLib.timeout_add(100, self.pulse)
        def worker():
            try:
                value = function(op)
                GLib.idle_add(done, value, None)
            except Exception as exc:
                # No source contents or arbitrary exception messages in logs.
                self.logger.error('%s: %s', self.t('error'), type(exc).__name__)
                GLib.idle_add(done, None, exc)
        def done(value, error):
            GLib.source_remove(timer)
            self.operation = None
            if self.progress_dialog:self.progress_dialog.destroy();self.progress_dialog=None
            for item in self.action_items:
                item.set_sensitive(True)
            for button, _ in self.buttons:
                button.set_sensitive(True)
            self.home.set_sensitive(True)
            self.destination.set_sensitive(True)
            self.cancel_item.set_sensitive(False)
            self.refresh_updates()
            self.status_key = 'cancelled' if isinstance(error, Cancelled) else 'error' if error else 'complete'
            self.status.set_text(self.t(self.status_key))
            self.logger.info('%s: %s',self.t(title_key),self.t(self.status_key))
            if self.closing:
                try:self.save_settings()
                except (OSError,ValueError):pass
                self.destroy()
                return False
            if error and not isinstance(error, Cancelled) and not quiet:
                code = str(error) if isinstance(error, ValueError) and str(error) in self.lang.packs['en']['strings'] else 'operation_failed'
                if isinstance(error,(URLError,TimeoutError)):code='network_error'
                detail=self.t('space_detail').format(required=f'{error.required/1024**3:.2f}',available=f'{error.available/1024**3:.2f}') if hasattr(error,'required') else ''
                self.message(code,detail)
            elif not error:
                finished(value)
            return False
        threading.Thread(target=worker, daemon=True).start()

    def show_progress(self,title_key,parent=None):
        window=Gtk.Window(title=self.t(title_key),transient_for=parent or self,modal=True,resizable=False)
        window.set_default_size(460,-1)
        window.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        window.set_name('saveconfig-progress')
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12,margin=20)
        window.add(box)
        self.progress_label=Gtk.Label(label=self.t(title_key),xalign=0,yalign=0,wrap=True,width_chars=50,max_width_chars=50)
        self.progress_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        context=self.progress_label.get_pango_context()
        metrics=context.get_metrics(context.get_font_description(),context.get_language())
        line_height=(metrics.get_ascent()+metrics.get_descent()+Pango.SCALE-1)//Pango.SCALE
        self.progress_text_scroll=Gtk.ScrolledWindow()
        self.progress_text_scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
        self.progress_text_scroll.set_min_content_height(4*line_height)
        self.progress_text_scroll.set_max_content_height(4*line_height)
        self.progress_text_scroll.set_propagate_natural_height(False)
        self.progress_text_scroll.add(self.progress_label)
        box.pack_start(self.progress_text_scroll,False,False,0)
        self.progress=Gtk.ProgressBar();box.pack_start(self.progress,False,False,0)
        self.progress_cancel=Gtk.Button(label=self.t('cancel'))
        self.progress_cancel.set_sensitive(self.operation_cancellable)
        self.progress_cancel.connect('clicked',self.cancel);box.pack_start(self.progress_cancel,False,False,0)
        window.connect('delete-event',self.close_progress)
        window.connect('map',lambda *_:center_after_map(window,parent or self))
        self.progress_dialog=window;window.show_all()

    def update_progress(self,op,message):
        if self.operation is op and self.progress_dialog and not op.cancel.is_set():
            self.progress_label.set_text(str(message))
        return False

    def pulse(self):
        if self.progress_dialog:
            if self.operation and hasattr(self.operation,"download_fraction"):self.progress.set_fraction(self.operation.download_fraction)
            else:self.progress.pulse()
            if self.operation and not self.operation.cancel.is_set() and hasattr(self.operation,'progress_target'):
                self.progress_label.set_text(self.operation.progress_target)
        return self.operation is not None

    def close_progress(self, window, *_):
        if self.operation and not self.operation_cancellable:
            return True
        self.cancel()
        window.destroy()
        self.progress_dialog = None
        return True

    def cancel(self, *_):
        if self.operation and self.operation_cancellable:
            self.operation.cancel.set()
            self.cancel_item.set_sensitive(False)
            if self.progress_dialog:self.progress_cancel.set_sensitive(False)

    def scan(self, *_):
        home = self.home.get_text()
        def complete(value):
            self.entries, self.status_key = value
            self.scan_home = home
            if self.profile_selection is not None:
                for entry in self.entries:
                    entry.selected = entry.path in self.profile_selection and entry.exists and entry.status != 'error' and not excluded_backup(entry)
            self.refresh()
            self.status.set_text(self.t(self.status_key))
            self.update_profile_label()
        self.start(lambda op: scan(self.db, home, op), complete,title_key='scan')

    def backup(self, *_):
        home, target = self.home.get_text(), self.destination.get_text()
        if self.scan_home != home:
            self.message('rescan_required')
            return
        if not target.strip():
            self.message('invalid_destination')
            return
        if any(e.selected and e.sensitive for e in self.entries) and not self.message('sensitive_confirm', question=True):
            return
        day = Path(target).expanduser() / datetime.now().strftime('%d.%m.%Y')
        if day.exists():
            if not self.message('daily_reuse_confirm', str(day), question=True):return
        def complete(value):
            self.last_backup, manifest = value
            self.status_key = manifest['status']
            self.status.set_text(self.t(self.status_key))
            self.message('backup_reused' if manifest.get('reused') else manifest['status'], str(self.last_backup)+'\n'+datetime.fromisoformat(manifest['date']).strftime('%d.%m.%Y %H:%M:%S'))
            if manifest.get('reused'):self.status.set_text(self.t('backup_reused'))
        self.start(lambda op: backup(self.db, home, target, self.entries, op, **{key:self.settings.data[key] for key in ('target_kind','mount_point','mount_source')}), complete,title_key='backup')

    def verify(self, *_):
        folder = self.choose(title='verify')
        if folder:
            def complete(errors):
                self.message('verification_failed' if errors else 'verified', '\n'.join(errors[:20]))
                with self.db.connect() as con:
                    con.execute('UPDATE backups SET verified=? WHERE backup_directory=?', (not errors, folder))
            self.start(lambda op: verify(folder, op), complete,title_key='verify')

    def show_backups(self, *_):
        folder = Path(self.destination.get_text())
        if not self.destination.get_text() or not folder.is_dir():
            self.message('invalid_destination')
            return
        def read(op):
            rows = []
            for child in sorted(folder.iterdir(), reverse=True):
                op.check()
                if child.is_dir() and not child.is_symlink() and (child / 'manifest.json').exists():
                    try:
                        m = load_manifest(child)
                        checked = False
                        sidecar = child / 'verification.json'
                        if sidecar.exists() and not sidecar.is_symlink():
                            checked = json.loads(sidecar.read_text()).get('verified', False)
                        rows.append((str(child), m, checked))
                    except (OSError, ValueError, KeyError):
                        rows.append((str(child), None, False))
            return rows
        def complete(rows):
            dialog = Gtk.Dialog(title=self.t('backups'), transient_for=self, modal=True)
            dialog.add_button(self.t('close'), Gtk.ResponseType.CLOSE)
            dialog.set_default_size(900, 450)
            model = Gtk.ListStore(str, str, str, str, str, str, str)
            for path, m, checked in rows:
                if m:
                    try:
                        date = datetime.fromisoformat(m['date']).strftime('%d.%m.%Y')
                    except ValueError:
                        date = '?'
                    model.append([date, m['hostname'], str(m['file_count']), str(m['total_size']), self.t('yes' if checked else 'no'), self.t(m['status']), path])
                else:
                    model.append(['?', '?', '?', '?', self.t('no'), self.t('error'), path])
            table = Gtk.TreeView(model=model)
            for i, key in enumerate(['date', 'hostname', 'files', 'size', 'verified', 'status', 'path']):
                table.append_column(Gtk.TreeViewColumn(self.t(key), Gtk.CellRendererText(), text=i))
            striped_rows(table)
            def content(_, path, column):
                location = model[path][6]
                try:
                    m = load_manifest(location)
                    self.message('contents', '\n'.join(f"{e['program'] or self.t('unknown')}: {e['backup']}" for e in m['entries']))
                except (OSError, ValueError, KeyError):
                    self.message('invalid_manifest')
            table.connect('row-activated', content)
            scroll = Gtk.ScrolledWindow()
            scroll.add(table)
            dialog.get_content_area().pack_start(scroll, True, True, 0)
            dialog.show_all()
            dialog.run()
            dialog.destroy()
        self.start(read, complete,title_key='backups')

    def restore(self, *_):
        folder = self.choose(title='restore')
        if not folder:
            return
        def complete(rows):
            details=[self.t('restore_integrity_note')]
            for r in rows:
                details.append(r['program']+'\n'+self.t(r['integrity'])+'\n'+self.t('source')+': '+r['source']+'\n'+self.t('target')+': '+r['target']+'\n'+self.t('exists')+': '+self.t('yes' if r['exists'] else 'no'))
            if rows and rows[0]['integrity_errors']:details.append('\n'.join(rows[0]['integrity_errors'][:20]))
            self.message('restore_phase_two','\n\n'.join(details))
        self.start(lambda op: preview(folder,self.home.get_text(),op),complete,title_key='restore')

    def learn(self, *_):
        model, iterator = self.view.get_selection().get_selected()
        if iterator is None:
            self.message('choose_row')
            return
        entry = self.entries[model[iterator][8]]
        dialog = Gtk.Dialog(title=self.t('learn'), transient_for=self, modal=True)
        dialog.add_buttons(self.t('cancel'), Gtk.ResponseType.CANCEL, self.t('save'), Gtk.ResponseType.OK)
        box = dialog.get_content_area()
        name = Gtk.Entry(text=entry.program)
        notes = Gtk.Entry()
        kind = Gtk.ComboBoxText()
        for code in ['config', 'profile', 'data', 'state', 'key', 'cache', 'system', 'unknown']:
            kind.append(code, self.t(code))
        kind.set_active_id(entry.kind)
        sensitive = Gtk.CheckButton(label=self.t('sensitive'))
        sensitive.set_active(entry.sensitive)
        selected = Gtk.CheckButton(label=self.t('selected'))
        selected.set_active(entry.selected)
        for key, widget in [('program', name), ('kind', kind), ('notes', notes)]:
            box.pack_start(Gtk.Label(label=self.t(key), xalign=0), False, False, 4)
            box.pack_start(widget, False, False, 4)
        box.pack_start(sensitive, False, False, 4)
        box.pack_start(selected, False, False, 4)
        dialog.show_all()
        if dialog.run() == Gtk.ResponseType.OK and name.get_text().strip():
            self.db.learn(name.get_text().strip(), '', entry.path, kind.get_active_id(), sensitive.get_active(), selected.get_active(), notes.get_text())
            entry.program, entry.kind, entry.sensitive, entry.selected, entry.known = name.get_text().strip(), kind.get_active_id(), sensitive.get_active(), selected.get_active(), True
            self.refresh()
        dialog.destroy()

    def language(self, *_):
        dialog = Gtk.Dialog(title=self.t('language'), transient_for=self, modal=True)
        dialog.add_buttons(self.t('cancel'), Gtk.ResponseType.CANCEL, self.t('save'), Gtk.ResponseType.OK)
        combo = Gtk.ComboBoxText()
        for code, pack in self.lang.packs.items():
            combo.append(code, self.lang.language_name(code))
        combo.set_active_id(self.settings.data['language'])
        dialog.get_content_area().pack_start(combo, False, False, 12)
        dialog.show_all()
        if dialog.run() == Gtk.ResponseType.OK and combo.get_active_id():
            self.settings.data['language'] = combo.get_active_id()
            self.settings.save()
            self.translate()
        dialog.destroy()

    def install_languages(self, *_, container=None, language_combo=None, source_entry=None):
        dialog = None if container is not None else Gtk.Dialog(title=self.t('install_languages'), transient_for=self, modal=True)
        if dialog:
            dialog.add_buttons(self.t('close'), Gtk.ResponseType.CLOSE)
        box = container if container is not None else dialog.get_content_area()
        owner=dialog or box.get_toplevel()
        source = source_entry or Gtk.Entry(text=PROJECT['source_url'])
        def refresh_choice(code):
            if language_combo is not None:
                language_combo.remove_all()
                for key, pack in self.lang.packs.items():
                    language_combo.append(key, self.lang.language_name(key))
                language_combo.set_active_id(code)
        def imported(_):
            chooser = Gtk.FileChooserDialog(title=self.t('import_language'), transient_for=owner, action=Gtk.FileChooserAction.OPEN)
            chooser.add_buttons(self.t('cancel'), Gtk.ResponseType.CANCEL, self.t('choose'), Gtk.ResponseType.OK)
            chooser.set_show_hidden(False)
            filter_=Gtk.FileFilter();filter_.set_name('JSON');filter_.add_pattern('*.json');chooser.add_filter(filter_)
            if chooser.run() == Gtk.ResponseType.OK:
                try:
                    from .utils import read_json_limited
                    pack = read_json_limited(chooser.get_filename(),2_000_000,'invalid_language')
                    self.lang.install(pack)
                    if language_combo is None:
                        self.settings.data['language'] = pack['code']
                        self.settings.save()
                        self.translate()
                    refresh_choice(pack['code'])
                except (ValueError, OSError, KeyError):
                    self.message('invalid_language')
            chooser.destroy()
        def catalog(_):
            base = PROJECT['source_url']
            if not base:self.message('no_source');return
            if language_combo is None:
                self.settings.data['github_source'] = PROJECT['source_url']
                self.settings.save()
            if dialog:
                dialog.response(Gtk.ResponseType.CLOSE)
            def loaded(items):
                if not items:
                    self.message('no_languages')
                    return
                choose = Gtk.Dialog(title=self.t('download_language'), transient_for=self, modal=True)
                choose.add_buttons(self.t('cancel'), Gtk.ResponseType.CANCEL, self.t('choose'), Gtk.ResponseType.OK)
                combo = Gtk.ComboBoxText()
                for item in items:
                    combo.append(item['code'], self.lang.language_name(item['code'],item['name']))
                combo.set_active(0)
                choose.get_content_area().add(combo)
                choose.show_all()
                response = choose.run()
                code = combo.get_active_id()
                choose.destroy()
                if response == Gtk.ResponseType.OK:
                    def installed(code):
                        if language_combo is None:
                            self.settings.data['language'] = code
                            self.settings.save()
                            self.translate()
                        refresh_choice(code)
                    self.start(lambda op: self.lang.download(base, code), installed,title_key='download_language',parent=owner if container is not None else self,save_paths=False,cancellable=False)
            self.start(lambda op: self.lang.catalog(base), loaded,title_key='download_language',parent=owner if container is not None else self,save_paths=False,cancellable=False)
        for key, callback in [('import_language', imported), ('download_language', catalog)]:
            button = Gtk.Button(label=self.t(key))
            button.connect('clicked', callback)
            if key=='download_language':button.set_sensitive(bool(PROJECT['source_url']))
            box.pack_start(button, False, False, 4)
        if dialog:
            dialog.show_all()
            dialog.run()
            dialog.destroy()

    def help(self, *_):
        code = self.settings.data['language']
        if code in ('de', 'en'):
            path = ROOT / 'help' / code / 'index.html'
        else:
            path = self.settings.root / '.local/share/saveconfig/help' / code / 'index.html'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.lang.packs.get(code, self.lang.packs['en'])['help_html'], encoding='utf-8')
        webbrowser.open(path.as_uri())

    def show_log(self, *_):
        from .log_dialog import show_log
        return show_log(self)

    def about(self, *_):
        dialog = Gtk.AboutDialog(transient_for=self, modal=True, use_header_bar=True, program_name='saveconfig', version=VERSION,
                                 comments=self.t('app_subtitle'), authors=[AUTHOR], license_type=Gtk.License.GPL_3_0_ONLY)
        try:
            dialog.set_logo(GdkPixbuf.Pixbuf.new_from_file_at_scale(str(ROOT / 'resources/saveconfig.png'), 128, 128, True))
        except GLib.Error:
            pass
        # GTK 3 also creates legacy action buttons in the header bar. Only the
        # stack switcher and the native window close control belong here.
        header = dialog.get_titlebar()
        for child in header.get_children():
            if isinstance(child, Gtk.StackSwitcher):
                stack = child.get_stack()
                for page in stack.get_children():
                    name = stack.child_get_property(page, 'name')
                    if name == 'main':
                        stack.child_set_property(page, 'title', 'Info')
                    elif name == 'credits':
                        stack.child_set_property(page, 'title', self.t('contributors'))
            else:
                child.set_no_show_all(True)
                child.hide()
        header.set_show_close_button(True)
        def wrap_description(widget):
            if isinstance(widget, Gtk.Label) and widget.get_text() == self.t('app_subtitle'):
                widget.set_line_wrap(True)
                widget.set_max_width_chars(55)
                widget.set_justify(Gtk.Justification.CENTER)
            if isinstance(widget, Gtk.Container):
                for child in widget.get_children():
                    wrap_description(child)
        wrap_description(dialog.get_content_area())
        dialog.connect('response', lambda widget, *_: widget.destroy())
        dialog.show()
        return dialog

    def update_profile_label(self):
        name = self.t('unsaved_profile')
        dirty = False
        valid = False
        ident = self.settings.data['active_profile']
        if ident:
            try:
                profile = self.profiles.get(ident)
                name = profile['name']
                valid = True
                dirty = self.home.get_text() != profile['home'] or self.destination.get_text() != profile['destination']
                dirty = dirty or any(self.settings.data[key]!=profile.get(key,'local' if key=='target_kind' else '') for key in ('smb_server','smb_share','target_kind','mount_point','mount_source'))
                if self.scan_home == self.home.get_text() and profile['selection_saved']:
                    dirty = dirty or {e.path for e in self.entries if e.selected} != set(profile['selection'])
            except (OSError, ValueError):
                pass
        suffix = ' (' + self.t('unsaved_changes') + ')' if dirty else ''
        context=self.profile_banner.get_style_context()
        if valid:context.add_class('active-profile')
        else:context.remove_class('active-profile')
        self.profile_icon.set_from_icon_name('document-edit-symbolic' if dirty else 'emblem-default-symbolic',Gtk.IconSize.LARGE_TOOLBAR)
        self.profile_label.set_text(self.t('active_profile') + ': ' + name + suffix)
        self.set_title(f'saveconfig {VERSION} – {name}' + suffix)

    def apply_profile(self, ident):
        if self.operation:
            return
        data = self.profiles.get(ident)
        self.home.set_text(data['home'])
        self.destination.set_text(data['destination'])
        self.profile_selection = set(data['selection']) if data['selection_saved'] else None
        self.entries = []
        self.scan_home = None
        self.last_backup = None
        self.settings.data.update(active_profile=ident, home=data['home'], destination=data['destination'],smb_server=data.get('smb_server',''),smb_share=data.get('smb_share',''),target_kind=data.get('target_kind','local'),mount_point=data.get('mount_point',''),mount_source=data.get('mount_source',''))
        self.settings.save()
        self.status_key = 'profile_loaded'
        self.translate()

    def show_profiles(self, *_):
        from .profile_dialog import show_profiles
        return show_profiles(self)

    def profile_choice(self):
        items = self.profiles.list()
        if not items:
            self.message('no_profiles')
            return None
        dialog = Gtk.Dialog(title=self.t('load_profile'), transient_for=self, modal=True)
        dialog.add_buttons(self.t('cancel'), Gtk.ResponseType.CANCEL, self.t('choose'), Gtk.ResponseType.OK)
        combo = Gtk.ComboBoxText()
        for ident, data in items:
            combo.append(ident, data['name'])
        combo.set_active(0)
        dialog.get_content_area().pack_start(combo, False, False, 12)
        dialog.show_all()
        result = combo.get_active_id() if dialog.run() == Gtk.ResponseType.OK else None
        dialog.destroy()
        return result

    def load_profile(self, *_):
        ident = self.profile_choice()
        if ident:
            self.apply_profile(ident)

    def save_profile(self, *_):
        dialog = Gtk.Dialog(title=self.t('save_profile'), transient_for=self, modal=True)
        dialog.add_buttons(self.t('cancel'), Gtk.ResponseType.CANCEL, self.t('save'), Gtk.ResponseType.OK)
        name = Gtk.Entry(placeholder_text=self.t('profile_name'))
        active = self.settings.data['active_profile']
        if active:
            try:
                name.set_text(self.profiles.get(active)['name'])
            except (OSError, ValueError):
                active = ''
        dialog.get_content_area().pack_start(name, False, False, 12)
        dialog.show_all()
        if dialog.run() == Gtk.ResponseType.OK:
            try:
                data = dict(format_version=1, name=name.get_text().strip(), home=self.home.get_text(), destination=self.destination.get_text(),smb_server=self.settings.data['smb_server'],smb_share=self.settings.data['smb_share'],target_kind=self.settings.data['target_kind'],mount_point=self.settings.data['mount_point'],mount_source=self.settings.data['mount_source'],
                            selection=[e.path for e in self.entries if e.selected] if self.scan_home == self.home.get_text() else list(self.profile_selection or []),
                            selection_saved=self.scan_home == self.home.get_text() or self.profile_selection is not None)
                ident = active if active and self.profiles.get(active)['name'] == data['name'] else None
                if ident and not self.message('overwrite_profile', question=True):
                    dialog.destroy()
                    return
                ident = self.profiles.save(data, ident)
                self.settings.data['active_profile'] = ident
                self.settings.save()
                self.profile_selection = set(data['selection']) if data['selection_saved'] else None
                self.update_profile_label()
            except (OSError, ValueError):
                self.message('invalid_profile')
        dialog.destroy()

    def profile_file_dialog(self, save=False):
        dialog = Gtk.FileChooserDialog(title=self.t('export_profile' if save else 'import_profile'), transient_for=self,
                                     action=Gtk.FileChooserAction.SAVE if save else Gtk.FileChooserAction.OPEN)
        dialog.add_buttons(self.t('cancel'), Gtk.ResponseType.CANCEL, self.t('choose'), Gtk.ResponseType.OK)
        filter_ = Gtk.FileFilter()
        filter_.set_name('JSON')
        filter_.add_pattern('*.json')
        dialog.add_filter(filter_)
        if save:
            dialog.set_current_name('saveconfig-profile.json')
        path = dialog.get_filename() if dialog.run() == Gtk.ResponseType.OK else None
        dialog.destroy()
        return path

    def import_profile(self, *_):
        path = self.profile_file_dialog()
        if path:
            try:
                self.apply_profile(self.profiles.import_file(path))
            except (OSError, ValueError):
                self.message('invalid_profile')

    def export_profile(self, *_):
        ident = self.profile_choice()
        if ident:
            path = self.profile_file_dialog(True)
            if path:
                try:
                    self.profiles.export(ident, path)
                except (OSError, ValueError):
                    self.message('profile_export_failed')

    def refresh_updates(self):
        for dialog in self.settings_dialogs[:]:
            controls=dialog.settings_controls
            controls['update_status'].set_text(self.t(self.update_status_key))
            newer=self.update_info and tuple(map(int,self.update_info['version'].split('.')))>tuple(map(int,VERSION.split('.')))
            controls['download'].set_sensitive(bool(newer and self.update_info.get('deb') and not self.operation and not self.update_check_running and not self.closing))

    def initial_update(self):
        self.check_update(automatic=True)
        return False

    def check_update(self,url=None,automatic=False,parent=None):
        from .updates import release_info
        if not self.alive or self.update_check_running:return
        if not PROJECT['update_url']:
            self.update_status_key='software_unconfigured';self.update_info=None;self.refresh_updates();return
        self.update_check_running=True;self.update_status_key='software_checking';self.refresh_updates()
        def finish(info,error):
            if not self.alive:return False
            self.update_check_running=False;self.update_info=info
            if error:
                self.update_status_key='software_check_failed'
                self.logger.warning(self.t('software_check_failed'))
            else:
                self.settings.data['last_update_check']=datetime.now(timezone.utc).isoformat()
                try:self.settings.save()
                except OSError:self.logger.error(self.t('operation_failed'))
                newer=tuple(map(int,info['version'].split('.')))>tuple(map(int,VERSION.split('.')))
                self.update_status_key='software_update' if newer else 'software_current'
            self.refresh_updates()
            return False
        def worker():
            try:info,error=release_info(PROJECT['update_url']),None
            except Exception as exc:info,error=None,exc
            GLib.idle_add(finish,info,error)
        threading.Thread(target=worker,daemon=True).start()

    def auto_update(self):
        data=self.settings.data
        if not self.alive or self.operation or not data['update_check']:return False
        try:last=datetime.fromisoformat(data['last_update_check'])
        except ValueError:last=datetime(1970,1,1,tzinfo=timezone.utc)
        if last.tzinfo is None:last=last.replace(tzinfo=timezone.utc)
        days={'days':1,'weeks':7,'months':30}[data['update_interval_unit']]*data['update_interval_value']
        if datetime.now(timezone.utc)-last>=timedelta(days=days):self.check_update(automatic=True)
        return False

    def download_available(self,*_):
        from .updates import download_update
        from .jobs import JobContext,Cancelled as DownloadCancelled
        if self.operation or self.update_check_running or not self.update_info:return
        info=self.update_info
        if not info.get('deb') or tuple(map(int,info['version'].split('.')))<=tuple(map(int,VERSION.split('.'))):return
        def task(op):
            def report(current,total):GLib.idle_add(self.download_progress,op,current,total)
            try:return download_update(info,JobContext(op.cancel,report))
            except DownloadCancelled:raise Cancelled('cancelled') from None
            except Exception:raise ValueError('update_download_error') from None
        self.start(task,lambda path:self.message('update_downloaded',str(path)),title_key='update_download',save_paths=False)

    def download_progress(self,op,current,total):
        if self.operation is op and self.progress_dialog:
            op.download_fraction=current/total
            self.progress.set_show_text(True)
            self.progress.set_fraction(current/total)
            self.progress.set_text(f'{round(current/total*100)} %')
        return False

    def show_info(self,*_):
        from .tool_info import show_info
        return show_info(self)

    def show_settings(self, *_):
        dialog=Gtk.Dialog(title=self.t('settings'),transient_for=self,modal=True)
        dialog.set_name('saveconfig-settings')
        dialog.set_default_size(650,620)
        dialog.add_buttons(self.t('cancel'),Gtk.ResponseType.CANCEL,self.t('save_settings'),Gtk.ResponseType.OK)
        scroll=Gtk.ScrolledWindow(vexpand=True,hscrollbar_policy=Gtk.PolicyType.NEVER)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10,margin=16)
        scroll.add(box);dialog.get_content_area().pack_start(scroll,True,True,0)
        def label(key):
            widget=Gtk.Label(label=self.t(key),xalign=0,wrap=True);box.pack_start(widget,False,False,0)
        def group(key):
            box.pack_start(Gtk.Separator(),False,False,4);label(key)
        label('source_settings')
        fields={}
        for key,value in [('home',self.home.get_text()),('destination',self.destination.get_text())]:
            label(key);field=Gtk.Entry(text=value);field.set_name(key);fields[key]=field
            row=Gtk.Box(spacing=8);row.pack_start(field,True,True,0)
            button=Gtk.Button(label=self.t('browse'));button.connect('clicked',lambda _,entry=field:self.choose(entry))
            row.pack_start(button,False,False,0);box.pack_start(row,False,False,0)
        label('profile_settings_hint')
        label('default_display')
        filter_controls={}
        for key,value in self.settings.data['display_filters'].items():
            if key=='cache':continue
            control=Gtk.CheckButton(label=self.t('filter_'+key));control.set_active(value)
            filter_controls[key]=control;box.pack_start(control,False,False,0)
        group('update_settings')
        update_check=Gtk.CheckButton(label=self.t('update_check'));update_check.set_active(self.settings.data['update_check'])
        box.pack_start(update_check,False,False,0)
        label('update_interval_label')
        interval=Gtk.Box(spacing=8);interval.pack_start(Gtk.Label(label=self.t('every')),False,False,0)
        count=Gtk.SpinButton.new_with_range(1,365,1);count.set_name('update_interval_value');count.set_value(self.settings.data['update_interval_value'])
        interval.pack_start(count,False,False,0)
        units=Gtk.ComboBoxText()
        for key in ('days','weeks','months'):units.append(key,self.t(key))
        units.set_active_id(self.settings.data['update_interval_unit']);interval.pack_start(units,False,False,0)
        box.pack_start(interval,False,False,0);label('update_interval_help')
        update_status=Gtk.Label(xalign=0,wrap=True);box.pack_start(update_status,False,False,0)
        download=Gtk.Button(label=self.t('update_download'));download.connect('clicked',self.download_available);box.pack_start(download,False,False,0)
        group('language_extensions');label('language')
        language=Gtk.ComboBoxText();language.set_name('installed_languages')
        for code in self.lang.packs:language.append(code,self.lang.language_name(code))
        language.set_active_id(self.settings.data['language'] if self.settings.data['language'] in self.lang.packs else 'en')
        box.pack_start(language,False,False,0)
        self.install_languages(container=box,language_combo=language)
        dialog.settings_controls=dict(language=language,fields=fields,update_check=update_check,count=count,units=units,update_status=update_status,download=download,filters=filter_controls)
        self.settings_dialogs.append(dialog)
        dialog.connect('destroy',lambda *_:self.settings_dialogs.remove(dialog) if dialog in self.settings_dialogs else None)
        self.refresh_updates()
        dialog.show_all()
        while dialog.run()==Gtk.ResponseType.OK:
            home=fields['home'].get_text().strip();destination=fields['destination'].get_text().strip()
            if not Path(home).is_absolute() or not Path(home).is_dir():self.message('invalid_home');continue
            if destination and not Path(destination).is_absolute():self.message('invalid_destination');continue
            count.update();new=dict(self.settings.data)
            new.update(home=home,destination=destination,language=language.get_active_id(),github_source=PROJECT['source_url'],
                       update_check=update_check.get_active(),update_interval_value=count.get_value_as_int(),update_interval_unit=units.get_active_id(),update_url=PROJECT['update_url'],
                       display_filters=dict(cache=False,**{key:control.get_active() for key,control in filter_controls.items()}))
            old=self.settings.data;self.settings.data=new
            try:self.settings.save()
            except OSError:
                self.settings.data=old;self.message('operation_failed');continue
            changed=home!=self.home.get_text();self.home.set_text(home);self.destination.set_text(destination)
            for key,value in new['display_filters'].items():
                if key in self.filter_widgets:self.filter_widgets[key].set_active(value)
            if changed:self.entries=[];self.scan_home=None;self.profile_selection=None
            self.translate();break
        dialog.destroy()

    def close(self, *_):
        if self.operation:
            if self.operation_cancellable:
                if self.message('confirm_close',question=True):self.closing=True;self.cancel()
            else:self.message('cancel_before_close')
            return True
        try:
            self.save_settings()
        except (OSError, ValueError):
            self.message('operation_failed')
            return True
        self.destroy()
        return False
