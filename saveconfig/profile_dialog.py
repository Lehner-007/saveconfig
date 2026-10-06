"""GTK-3-Profilverwaltung mit Liste links und Profilfeldern rechts."""
from copy import deepcopy
from gi.repository import Gtk
from .presentation import center_after_map
from .utils import atomic_json


def show_profiles(owner):
    previous=getattr(owner,'profiles_dialog',None)
    if previous and previous.get_visible():
        previous.present()
        return previous
    dialog=Gtk.Dialog(title=owner.t('profiles'),transient_for=owner,modal=True)
    owner.profiles_dialog=dialog
    dialog.set_default_size(720,440)
    dialog.add_button(owner.t('cancel'),Gtk.ResponseType.CANCEL)
    dialog.add_button(owner.t('save'),Gtk.ResponseType.APPLY)
    dialog.add_button(owner.t('profile_apply'),Gtk.ResponseType.OK)
    layout=Gtk.Box(spacing=16,margin=16)
    dialog.get_content_area().pack_start(layout,True,True,0)
    left=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8)
    layout.pack_start(left,False,False,0)
    listing=Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
    scroll=Gtk.ScrolledWindow();scroll.set_size_request(200,180);scroll.add(listing)
    left.pack_start(scroll,True,True,0)
    right=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8,hexpand=True)
    right_scroll=Gtk.ScrolledWindow();right_scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);right_scroll.add(right)
    layout.pack_start(right_scroll,True,True,0)
    fields={}
    for key,label in [('name','profile_name'),('home','home'),('destination','destination'),('smb_server','smb_server'),('smb_share','smb_share'),('target_kind','target_kind'),('mount_point','mount_point'),('mount_source','mount_source')]:
        right.pack_start(Gtk.Label(label=owner.t(label),xalign=0),False,False,0)
        field=Gtk.ComboBoxText() if key=='target_kind' else Gtk.Entry()
        if key=='target_kind':
            field.append('local',owner.t('target_local'));field.append('network',owner.t('target_network'))
        fields[key]=field
        if key!='name':field.set_direction(Gtk.TextDirection.LTR)
        right.pack_start(field,False,False,0)
    selection_label=Gtk.Label(xalign=0,wrap=True)
    right.pack_start(selection_label,False,False,0)
    items={key:deepcopy(value) for key,value in owner.profiles.list()}
    for value in items.values():
        for key in ('smb_server','smb_share','target_kind','mount_point','mount_source'):value.setdefault(key,'local' if key=='target_kind' else '')
    original=set(items)
    state={'key':None,'refresh':False}

    def current_values():
        return dict(format_version=1,name='',home=owner.home.get_text(),destination=owner.destination.get_text(),smb_server=owner.settings.data['smb_server'],smb_share=owner.settings.data['smb_share'],target_kind=owner.settings.data['target_kind'],mount_point=owner.settings.data['mount_point'],mount_source=owner.settings.data['mount_source'],
                    selection=[e.path for e in owner.entries if e.selected] if owner.scan_home==owner.home.get_text() else list(owner.profile_selection or []),
                    selection_saved=owner.scan_home==owner.home.get_text() or owner.profile_selection is not None)

    def commit():
        key=state['key']
        if key:
            value=dict(items[key],**{name:(field.get_active_id() or 'local') if name=='target_kind' else field.get_text().strip() for name,field in fields.items()})
            owner.profiles.validate(value)
            if any(other!=key and data['name'].casefold()==value['name'].casefold() for other,data in items.items()):
                raise ValueError('invalid_profile')
            items[key]=value
            for row in listing.get_children():
                if row.profile_id==key:row.get_child().set_text(value['name'])

    def selected(_,row):
        if state['refresh']:return
        try:commit()
        except ValueError:
            owner.message('invalid_profile');state['refresh']=True
            listing.select_row(next((r for r in listing.get_children() if r.profile_id==state['key']),None))
            state['refresh']=False;return
        key=row.profile_id if row else None;state['key']=key
        right.set_sensitive(key is not None)
        for name,field in fields.items():
            if name=='target_kind':field.set_active_id(items[key][name] if key else 'local')
            else:field.set_text(items[key][name] if key else '')
        selection_label.set_text(owner.t('profile_selection_count').format(count=len(items[key]['selection'])) if key else '')

    def refresh(key=None):
        state['refresh']=True
        for row in listing.get_children():listing.remove(row)
        target=None
        for ident,value in sorted(items.items(),key=lambda item:item[1]['name'].casefold()):
            row=Gtk.ListBoxRow();row.profile_id=ident
            row.add(Gtk.Label(label=value['name'],xalign=0,margin=8));listing.add(row)
            if ident==key:target=row
        state['key']=None;state['refresh']=False;listing.show_all();listing.select_row(target)
        if target is None:selected(listing,None)

    def create(*_):
        import uuid
        try:commit()
        except ValueError:owner.message('invalid_profile');return
        value=current_values();number=1
        while owner.t('new_profile_name').format(number=number).casefold() in {v['name'].casefold() for v in items.values()}:number+=1
        value['name']=owner.t('new_profile_name').format(number=number)
        key=uuid.uuid4().hex;items[key]=value;refresh(key)

    def remove(*_):
        key=state['key']
        if key:
            del items[key];refresh()

    def response(_,code):
        if code not in (Gtk.ResponseType.OK,Gtk.ResponseType.APPLY):dialog.destroy();return
        try:
            commit()
            # Validate the whole staged list before touching persisted profiles.
            for value in items.values():owner.profiles.validate(value)
            for key in original:
                owner.profiles.get(key)
            for key,value in items.items():
                atomic_json(owner.profiles.folder/(key+'.json'),value)
            for key in original-set(items):
                path=owner.profiles.folder/(key+'.json')
                if path.is_symlink():raise ValueError('invalid_profile')
                path.unlink()
            if code==Gtk.ResponseType.OK and state['key']:owner.apply_profile(state['key'])
            elif owner.settings.data['active_profile'] not in items:
                owner.settings.data['active_profile']='';owner.profile_selection=None;owner.settings.save()
            owner.update_profile_label();dialog.destroy()
        except (OSError,ValueError):owner.message('invalid_profile')

    actions=Gtk.Box(spacing=8)
    new=Gtk.Button(label=owner.t('profile_new'));new.connect('clicked',create);actions.pack_start(new,True,True,0)
    delete=Gtk.Button(label=owner.t('profile_delete'));delete.connect('clicked',remove);actions.pack_start(delete,True,True,0)
    left.pack_start(actions,False,False,0)
    transfer=Gtk.Box(spacing=8)
    for label,callback in [('import_profile',owner.import_profile),('export_profile',owner.export_profile)]:
        button=Gtk.Button(label=owner.t(label));button.connect('clicked',lambda _,fn=callback:(dialog.destroy(),fn()))
        transfer.pack_start(button,True,True,0)
    right.pack_end(transfer,False,False,0)
    listing.connect('row-selected',selected);dialog.connect('response',response)
    dialog.connect('map',lambda *_:center_after_map(dialog,owner))
    dialog.profile_controls=dict(list=listing,fields=fields,new=new,delete=delete,items=items)
    refresh(owner.settings.data['active_profile'] or None)
    dialog.show_all();return dialog
