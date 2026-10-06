"""Gemeinsame Darstellung, angepasst an Saveconfigs vorhandenes GTK 3."""
from gi.repository import Gtk,Gdk,GLib


def style_menus(bar):
    bar.get_style_context().add_class('saveconfig-menubar')
    provider=Gtk.CssProvider()
    provider.load_from_data(b'''
        .saveconfig-menu separator {
            min-height: 1px;
            background-color: alpha(@theme_fg_color, 0.45);
            margin-top: 4px; margin-bottom: 4px;
        }
    ''')
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    return provider


def striped_rows(view):
    """Die aktuelle sichtbare/sortierte Reihenfolge bestimmt den Zeilenwechsel."""
    view._stripe_hover=None
    def paint(column,renderer,model,iterator,*_):
        path=model.get_path(iterator)
        selected=view.get_selection().path_is_selected(path)
        stripe=path.get_indices()[0]%2==1 and not selected and str(path)!=view._stripe_hover
        renderer.set_property('cell-background-set',stripe)
        if stripe:
            found,color=view.get_style_context().lookup_color('theme_fg_color')
            if not found:color=view.get_style_context().get_color(Gtk.StateFlags.NORMAL)
            color.alpha=.09
            renderer.set_property('cell-background-rgba',color)
    for column in view.get_columns():
        for renderer in column.get_cells():column.set_cell_data_func(renderer,paint)
    def hover(widget,event):
        hit=widget.get_path_at_pos(int(event.x),int(event.y))
        widget._stripe_hover=str(hit[0]) if hit else None
        widget.queue_draw()
        return False
    def leave(widget,event):
        widget._stripe_hover=None;widget.queue_draw();return False
    view.add_events(Gdk.EventMask.POINTER_MOTION_MASK|Gdk.EventMask.LEAVE_NOTIFY_MASK)
    view.connect('motion-notify-event',hover)
    view.connect('leave-notify-event',leave)
    view.get_selection().connect('changed',lambda *_:view.queue_draw())


def reachable_bounds(rect,monitors):
    if not monitors:return (0,0,760,480)
    x,y,width,height=rect
    def overlap(m):
        left,top,w,h=m
        return max(0,min(x+width,left+w)-max(x,left))*max(0,min(y+height,top+h)-max(y,top))
    monitor=max(monitors,key=overlap)
    left,top,mw,mh=monitor
    width=min(max(360,width),max(1,mw-32));height=min(max(240,height),max(1,mh-80))
    if overlap(monitor)==0:x,y=left+(mw-width)//2,top+(mh-height-40)//2
    return (max(left+16,min(x,left+mw-width-16)),max(top+16,min(y,top+mh-height-64)),width,height)


def monitor_rects():
    display=Gdk.Display.get_default()
    result=[]
    for i in range(display.get_n_monitors()):
        r=display.get_monitor(i).get_workarea()
        result.append((r.x,r.y,r.width,r.height))
    return result


def center_after_map(dialog,parent):
    def position():
        if dialog.get_window() and parent.get_window():
            p=parent.get_window().get_frame_extents();d=dialog.get_window().get_frame_extents()
            dialog.move(p.x+(p.width-d.width)//2,p.y+(p.height-d.height)//2)
        return False
    GLib.timeout_add(100,position)
    GLib.timeout_add(250,position)
