"""Lesende Protokollanzeige und Export des sichtbaren Stands."""
from gi.repository import Gtk
from pathlib import Path
from .presentation import center_after_map


def show_log(owner):
    old=getattr(owner,'log_dialog',None)
    if old and old.get_visible():old.present();return old
    dialog=Gtk.Dialog(title=owner.t('log'),transient_for=owner)
    owner.log_dialog=dialog;dialog.set_default_size(780,480)
    dialog.add_button(owner.t('close'),Gtk.ResponseType.CLOSE)
    box=dialog.get_content_area();box.set_spacing(8);box.set_border_width(12)
    path=owner.settings.root/'.local/state/saveconfig/logs/saveconfig.log'
    box.pack_start(Gtk.Label(label=str(path),xalign=0,wrap=True,selectable=True),False,False,0)
    box.pack_start(Gtk.Label(label=owner.t('log_readonly'),xalign=0,wrap=True),False,False,0)
    view=Gtk.TextView(editable=False,cursor_visible=False,monospace=True,wrap_mode=Gtk.WrapMode.WORD_CHAR)
    scroll=Gtk.ScrolledWindow();scroll.add(view);box.pack_start(scroll,True,True,0)
    def reload(*_):
        try:
            for handler in owner.logger.handlers:handler.flush()
            if not path.exists():text=''
            else:
                with path.open('rb') as stream:
                    stream.seek(0,2);start=max(0,stream.tell()-1_000_000);stream.seek(start)
                    if start:stream.readline()
                    text=stream.read().decode('utf-8',errors='replace')
            view.get_buffer().set_text(text)
        except OSError:owner.message('log_error')
    def export(*_):
        chooser=Gtk.FileChooserDialog(title=owner.t('log_export'),transient_for=dialog,action=Gtk.FileChooserAction.SAVE)
        chooser.add_buttons(owner.t('cancel'),Gtk.ResponseType.CANCEL,owner.t('save'),Gtk.ResponseType.OK)
        chooser.set_current_name('saveconfig-protokoll.txt')
        filter_=Gtk.FileFilter();filter_.set_name('Text');filter_.add_pattern('*.txt');chooser.add_filter(filter_)
        if chooser.run()==Gtk.ResponseType.OK:
            try:
                buffer=view.get_buffer()
                with Path(chooser.get_filename()).open('x',encoding='utf-8') as target:
                    target.write(buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),True))
            except OSError:owner.message('log_error')
        chooser.destroy()
    buttons=Gtk.Box(spacing=8)
    refresh=Gtk.Button(label=owner.t('log_reload'));refresh.connect('clicked',reload)
    save=Gtk.Button(label=owner.t('log_export'));save.connect('clicked',export)
    buttons.pack_start(refresh,False,False,0);buttons.pack_start(save,False,False,0);box.pack_start(buttons,False,False,0)
    dialog.connect('response',lambda widget,*_:widget.destroy())
    dialog.connect('map',lambda *_:center_after_map(dialog,owner))
    dialog.log_controls=dict(view=view,reload=refresh,export=save)
    reload();dialog.show_all();return dialog
