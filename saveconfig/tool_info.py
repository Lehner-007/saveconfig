"""Read-only dependency information for the existing GTK 3 application."""
import importlib.util,importlib.metadata,platform,shutil,subprocess,threading
from gi.repository import Gtk,GLib
from .presentation import center_after_map
TOOLS=[dict(name='Python',kind='python',apt='python3'),dict(name='GTK',kind='gtk',apt='gir1.2-gtk-3.0'),dict(name='PyGObject',kind='module',module='gi',distribution='PyGObject',apt='python3-gi'),dict(name='requests',kind='module',module='requests',apt='python3-requests'),dict(name='dpkg-query',kind='command',command='dpkg-query',apt='dpkg'),dict(name='apt-mark',kind='command',command='apt-mark',apt='apt')]

def inspect_tool(tool):
 result=dict(tool,available=False,version='')
 try:
  if tool['kind']=='python':result.update(available=True,version=platform.python_version())
  elif tool['kind']=='gtk':result.update(available=True,version='.'.join(map(str,(Gtk.get_major_version(),Gtk.get_minor_version(),Gtk.get_micro_version()))))
  elif tool['kind']=='module':
   result['available']=importlib.util.find_spec(tool['module']) is not None
   if result['available']:
    try:result['version']=importlib.metadata.version(tool.get('distribution',tool['module']))
    except importlib.metadata.PackageNotFoundError:
     import importlib as importer
     result['version']=str(getattr(importer.import_module(tool['module']),'__version__',''))
  else:
   command=shutil.which(tool['command'])
   if command:
    result['available']=True
    proc=subprocess.run([command,'--version'],capture_output=True,text=True,timeout=5)
    lines=(proc.stdout or proc.stderr).splitlines()
    if proc.returncode==0 and lines:result['version']=lines[0][:500]
 except (ImportError,OSError,ValueError,subprocess.SubprocessError):pass
 return result

def show_info(owner):
 if owner.info_window and owner.info_window.get_visible():owner.info_window.present();return owner.info_window
 window=Gtk.Window(title=owner.t('info'),transient_for=owner)
 owner.info_window=window
 window.set_default_size(620,480)
 box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=16,margin=20);window.add(box)
 heading=Gtk.Box(spacing=10)
 heading.pack_start(Gtk.Image.new_from_icon_name('dialog-information-symbolic',Gtk.IconSize.LARGE_TOOLBAR),False,False,0)
 title=Gtk.Label(label=owner.t('tool_info_title'),xalign=0);heading.pack_start(title,True,True,0);box.pack_start(heading,False,False,0)
 scroll=Gtk.ScrolledWindow();scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
 content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=16);scroll.add(content);box.pack_start(scroll,True,True,0)
 content.pack_start(Gtk.Label(label=owner.t('tool_info_loading'),xalign=0),False,False,0)
 close=Gtk.Button(label=owner.t('close'));close.connect('clicked',lambda *_:window.destroy());box.pack_start(close,False,False,0)
 def forget(*_):
  if owner.info_window is window:owner.info_window=None
 window.connect('destroy',forget)
 def render(results):
  if not owner.alive or owner.info_window is not window:return False
  for child in content.get_children():content.remove(child)
  for tool in results:
   row=Gtk.Box(spacing=10)
   icon=Gtk.Image.new_from_icon_name('emblem-ok-symbolic' if tool['available'] else 'dialog-warning-symbolic',Gtk.IconSize.BUTTON);icon.set_valign(Gtk.Align.START);row.pack_start(icon,False,False,0)
   detail=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3)
   texts=[tool['name']+' — '+owner.t('tool_available' if tool['available'] else 'tool_missing')]
   if tool['version']:texts.append(tool['version'])
   texts.append('APT: '+tool['apt'])
   for text in texts:detail.pack_start(Gtk.Label(label=text,xalign=0,wrap=True,selectable=True),False,False,0)
   row.pack_start(detail,True,True,0);content.pack_start(row,False,False,0)
  window.tool_results=results
  window.refresh_info=lambda:(window.set_title(owner.t('info')),title.set_text(owner.t('tool_info_title')),close.set_label(owner.t('close')),render(results))
  content.show_all()
  return False
 threading.Thread(target=lambda:GLib.idle_add(render,[inspect_tool(t) for t in TOOLS]),daemon=True).start()
 window.connect('map',lambda *_:center_after_map(window,owner));window.show_all();return window
