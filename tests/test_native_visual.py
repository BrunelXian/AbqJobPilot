"""Real Tk HWND captures; one product root across languages, no service/Solver."""
import ctypes
import json
from test_native_workspace import desktop
from cockpit_capture import capture


def hwnd(app):
    api=ctypes.WinDLL('user32',use_last_error=True)
    api.GetAncestor.argtypes=[ctypes.c_void_p,ctypes.c_uint];api.GetAncestor.restype=ctypes.c_void_p
    return api.GetAncestor(app.winfo_id(),2)


def test_actual_native_pages_five_languages_themes_and_skins(desktop,tmp_path):
    app,w=desktop
    for locale in ('en','zh-CN','ja-JP','fr-FR','de-DE'):
        root=tmp_path/'captures'/locale;root.mkdir(parents=True)
        w.change_language(locale)
        for key in (key for key in w.pages if key!='classic'):
            app.geometry('1366x900')
            w.navigate(key);app.update();capture(hwnd(app),root/(key+'.png'))
            assert w.pages[key].winfo_ismapped()
        for skin in ('default','babbo'):
            w.change_skin(skin)
            for appearance in ('light','dark'):
                w.change_appearance(appearance);w.navigate('overview');w.drawer.grid_remove()
                for geometry in ('1024x768','1920x1080'):
                    app.geometry(geometry+'+0+0');app.update();app.update_idletasks()
                    name=f'{locale}_{skin}_{appearance}_{geometry.replace("x","_")}.png'
                    capture(hwnd(app),root/name)
                    edge=app.winfo_rootx()+app.winfo_width()
                    assert w.language_box.winfo_rootx()+w.language_box.winfo_width()<=edge
                    assert w.appearance_box.winfo_rootx()+w.appearance_box.winfo_width()<=edge
                    assert w.start_queue_button.winfo_rootx()+w.start_queue_button.winfo_width()<=edge
                    for control in (w.project_selector,w.add_task_button,w.command_button,
                                    w.start_queue_button,w.service_toolbar_button):
                        assert control.winfo_width()>=control.winfo_reqwidth()
                        assert control.winfo_rootx()+control.winfo_width()<=edge
                    assert w.queue_tree.winfo_rooty()<app.winfo_rooty()+200
                    assert w.queue_tree.winfo_height()>80
                    assert w.queue_tree.cget('style')=='Cockpit.Treeview'
                    assert int(float(app.tk.call('tk','scaling')))>=1
                    assert w.font_size>=10
                    assert all(child.winfo_class()!='TEntry' for child in w.queue_tree.master.winfo_children() if child is not w.queue_tree)
                assert w.log_widgets['progress'].winfo_height()>40 and w.log_widgets['events'].winfo_height()>40
        (root/'measurements.json').write_text(json.dumps({'locale':locale,'tk_scaling':app.tk.call('tk','scaling'),
            'geometries':['1024x768','1920x1080'],'skins':['default','babbo'],'appearances':['light','dark'],
            'runtime':'native Tk 8.6','project':'none','abaqus_calls':0},indent=2),encoding='utf-8')
    w.change_language('en');app.geometry('1366x900+0+0')
    w.change_skin('default');w.change_appearance('light')
