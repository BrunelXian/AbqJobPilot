"""Real Tk HWND captures; one product root across languages, no service/Solver."""
import ctypes
import json
from test_native_workspace import desktop
from cockpit_capture import capture


def hwnd(app):
    api=ctypes.WinDLL('user32',use_last_error=True)
    api.GetAncestor.argtypes=[ctypes.c_void_p,ctypes.c_uint];api.GetAncestor.restype=ctypes.c_void_p
    return api.GetAncestor(app.winfo_id(),2)


def test_actual_native_pages_wizard_languages_and_classic(desktop,tmp_path):
    app,w=desktop
    for locale in ('en','zh-CN','fr-FR','de-DE'):
        app.geometry('1366x900');w.change_language(locale);app.update()
        root=tmp_path/'captures'/locale;root.mkdir(parents=True)
        for key in w.pages:
            w.navigate(key);app.update();capture(hwnd(app),root/(key+'.png'))
            assert w.pages[key].winfo_ismapped()
        w.new_project();app.update();capture(hwnd(w.dialog),root/'wizard.png')
        d=w.dialog
        for widget in d.winfo_children():
            if widget.winfo_ismapped():
                assert widget.winfo_rooty()+widget.winfo_height()<=d.winfo_rooty()+d.winfo_height(),str(widget)
        d.destroy()
        app.geometry('1024x768');w.navigate('settings');app.update();capture(hwnd(app),root/'narrow.png')
        assert w.classic_button.winfo_ismapped() and w.language_box.winfo_ismapped()
        (root/'measurements.json').write_text(json.dumps({'locale':locale,'tk_scaling':app.tk.call('tk','scaling'),
            'actual_geometry':app.geometry(),'page_count':len(w.pages),'runtime':'native Tk 8.6','abaqus_calls':0},indent=2),encoding='utf-8')
    w.change_language('en');app.geometry('1366x900')
    from abqjobpilot.project import ProjectManager
    project=ProjectManager(recent_file=tmp_path/'recent.json').create_project(tmp_path/'classic','Classic Review')
    w.open_classic(project.root);app.update()
    assert w.classic_pane is not None
    capture(hwnd(app),tmp_path/'classic_connected.png')
    w.back_button.invoke();app.update();capture(hwnd(app),tmp_path/'execution_return.png')
    assert w.current_page=='runs' and w.classic_pane.project_manager.current.project_id==project.project_id
