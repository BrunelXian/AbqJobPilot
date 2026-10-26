"""Native Tk display tests, explicit temporary Runtime/Recent/preferences only."""
import json
import hashlib
import time
from pathlib import Path
from string import Formatter
from unittest.mock import patch
import pytest
from abqjobpilot.ui_resources import LANGUAGES, catalog, translate, DisplayPreferences
from abqjobpilot.gui_app import AbqJobPilotApp


@pytest.fixture
def desktop(tmp_path,monkeypatch,request):
    monkeypatch.setenv('ABQJOBPILOT_UI_PREFS',str(tmp_path/'display.json'))
    monkeypatch.setenv('USERPROFILE',str(tmp_path/'home'))
    monkeypatch.setenv('HOME',str(tmp_path/'home'))
    if hasattr(request.node,'callspec') and 'scale' in request.node.callspec.params:
        from abqjobpilot import cockpit_layout
        build=cockpit_layout.build_cockpit
        def scaled_build(workspace):
            workspace.app.tk.call('tk','scaling',96/72*request.node.callspec.params['scale'])
            build(workspace)
        monkeypatch.setattr(cockpit_layout,'build_cockpit',scaled_build)
    with patch('subprocess.Popen',side_effect=AssertionError('No execution from display')):
        app=AbqJobPilotApp(attachment_mode=True,native_workspace=True)
        errors=[];app.report_callback_exception=lambda *args:errors.append(str(args))
        try:
            app.update();yield app,app.execution_view
        finally:
            app.destroy()
            for reader in app.execution_view.readers:reader.thread.join(8);assert not reader.thread.is_alive()
            for thread in app.execution_view.lifecycle_threads:thread.join(8);assert not thread.is_alive()
            assert not errors,errors


def test_empty_navigation_single_root_no_default_runtime(desktop,tmp_path):
    app,w=desktop
    for key in w.pages:
        w.navigate(key);app.update();assert w.current_page==key
        assert w.pages[key].winfo_ismapped()
    w.classic_button.invoke();assert w.current_page=='classic'
    w.back_button.invoke();assert w.current_page=='runs'
    assert w.reader is None and w.classic_pane is None
    assert not list(tmp_path.rglob('execution.sqlite3'))
    assert not list(tmp_path.rglob('queue.json'))
    assert not list(tmp_path.rglob('connection.json'))


@pytest.mark.parametrize('locale',list(LANGUAGES))
def test_catalog_complete_parameters_and_native_language(desktop,locale):
    app,w=desktop
    en=catalog('en');other=catalog(locale);assert en.keys()==other.keys()
    fields=lambda v:{field for _,field,_,_ in Formatter().parse(v) if field}
    for key in en:assert fields(en[key])==fields(other[key]),key
    w.change_language(locale);app.update()
    assert w.classic_button.cget('text')==other['classic']
    assert DisplayPreferences(w.preferences.path).data['language']==locale
    assert translate(locale,'no_such_key')!= 'no_such_key'
    assert translate(locale,'observed',time='12:00').endswith('12:00')


def test_locale_fallback_is_display_only(tmp_path):
    p=tmp_path/'prefs.json';p.write_text('{"language":"unsupported"}',encoding='utf-8')
    preferences=DisplayPreferences(p);assert preferences.data['language']=='en'
    preferences.save(language='de-DE',grant='forbidden',dispatch='OPEN')
    assert 'grant' not in p.read_text() and 'dispatch' not in p.read_text()
    assert translate('invalid','open')=='Open Project'


def test_classic_native_navigation_preserves_widgets_and_raw_status(desktop,tmp_path):
    app,w=desktop
    from abqjobpilot import config
    from abqjobpilot.project import ProjectManager
    from abqjobpilot.queue_store import build_queue_record,save_queue
    from abqjobpilot.gui_presentation import status_presentation,filter_jobs
    project=ProjectManager(recent_file=tmp_path/'recent.json').create_project(tmp_path/'classic','Classic')
    inp=tmp_path/'bar.inp';inp.write_text('*Heading\n')
    records=[]
    for state in ('QUEUED','UNKNOWN_INTERRUPTED','FAILED_FATAL'):
        r=build_queue_record(inp,1,0,'b','b',None,False,False,'');r['status']=state;records.append(r)
    save_queue(records,runtime_dir=project.runtime_dir)
    before=hashlib.sha256((project.runtime_dir/'queue.json').read_bytes()).hexdigest()
    with patch('abqjobpilot.desktop_workspace.messagebox.showerror') as err:
        w.open_classic(project.root);assert not err.called,err.call_args
    pane=w.classic_pane;assert pane is not None
    pane.queue_tree.selection_set(records[0]['queue_id']);pane.queue_search_var.set('bar')
    app.update();runner=pane.runner
    for _ in range(3):
        w.back_button.invoke();w.classic_button.invoke();app.update()
        assert w.classic_pane is pane and pane.runner is runner
        assert pane.queue_search_var.get()=='bar'
    w.command_button.invoke();app.update()
    assert w.current_page=='overview' and w.classic_pane is pane and pane.runner is runner
    assert w.reader is None and not w.lifecycle_threads
    assert pane.queue_tree.selection()==(records[0]['queue_id'],)
    assert hashlib.sha256((project.runtime_dir/'queue.json').read_bytes()).hexdigest()==before
    assert status_presentation('UNKNOWN_INTERRUPTED')[0]=='Interrupted (Unverified)'
    assert status_presentation('FAILED_FATAL')[0]=='Failed'
    assert [r['status'] for r in filter_jobs(records,status_filter='interrupted')]==['UNKNOWN_INTERRUPTED']
    assert [r['status'] for r in filter_jobs(records,status_filter='failed')]==['FAILED_FATAL']
    assert config.RUNTIME_DIR==str(project.runtime_dir)


def test_new_project_dialog_is_explicit_abaqus_no_process(desktop):
    app,w=desktop;w.new_button.invoke();app.update()
    assert w.dialog.title()=='New Project'
    assert w.lifecycle_threads==[]
    assert len([c for c in app.winfo_children() if c.winfo_class()=='Toplevel'])==1
    choices=[c for c in w.dialog.winfo_children() if c.winfo_class()=='TCombobox']
    assert len(choices)==1 and choices[0].get()=='Abaqus'
    assert choices[0].cget('values')==('Abaqus',)
    w.dialog.destroy()


def test_display_recovery_uses_core_projection_without_apply(desktop):
    app,w=desktop
    from abqjobpilot.execution.supervisor import OPERATIONS
    assert 'apply_interrupted_recovery' not in OPERATIONS
    assert 'inspect_interrupted_execution' in OPERATIONS and 'preview_interrupted_recovery' in OPERATIONS
    # Offline immutable display contract, not executed Run evidence.
    run={'run_id':'r_display','plan_id':'plan_display','job_id':'job_display','backend_id':'python-process-fixture-v1',
         'execution':'UNKNOWN','reconciliation':'REQUIRED','artifact_validation':'NOT_RUN'}
    value={'connected':True,'observed_at':'2026-10-25T00:00:00Z','endpoint':{'project_id':'p_display','project_instance_id':'i_display','owner_id':'o_display'},
           'run':run,'receipt':None,'gate':{'state':'PAUSED'},'validations':[],'progress':[],'events':[],
           'interruption':{'body':{'diagnosis':{'display_projection':'UNKNOWN_INTERRUPTED'},'reason_evidence':['MISSING_EXIT'],'unknowns':['UNKNOWN']}},
           'recovery':{'body':{'decision':'KEEP_BLOCKED','apply_allowed':False}}}
    original=json.dumps(value,sort_keys=True)
    w._render(value)
    assert 'Interrupted (Unverified)' in w.detail_boxes['evidence'].get('1.0','end')
    assert 'KEEP_BLOCKED' in w.detail_boxes['recovery'].get('1.0','end')
    w._render({'connected':False,'code':'COMMUNICATION_UNKNOWN'})
    assert 'cached' not in w.status.get() or not w.connected
    assert 'UNKNOWN' in w.detail_boxes['identity'].get('1.0','end')
    w.change_language('de-DE');assert not w.connected and 'Verbindung' in w.status.get()
    assert json.dumps(value,sort_keys=True)==original


@pytest.mark.parametrize('scale',[1.0,1.25,1.5])
def test_native_sizes_and_local_scaling(desktop,scale,tmp_path):
    app,w=desktop
    app.tk.call('tk','scaling',96/72*scale)
    app.geometry('1366x768');w.change_language('de-DE');app.update()
    assert w.classic_button.winfo_width()>=w.classic_button.winfo_reqwidth()
    for key in w.pages:
        w.navigate(key);app.update()
        assert w.classic_button.winfo_ismapped()
        assert w.command_button.winfo_rootx()+w.command_button.winfo_width()<app.winfo_rootx()+app.winfo_width()
    assert w.language_box.winfo_rootx()+w.language_box.winfo_width()<=app.winfo_rootx()+app.winfo_width()

    from cockpit_capture import capture
    from test_native_visual import hwnd
    from tkinter import font
    import ctypes
    w.navigate('overview');w.drawer.grid_remove();app.update()
    capture(hwnd(app),tmp_path/('scaling_'+str(scale)+'.png'))
    metrics=font.Font(app,family='Segoe UI',size=10,weight='bold')
    for tree in (w.queue_tree,w.results_tree):
        for col in tree['columns']:assert tree.column(col,'minwidth')>=metrics.measure(tree.heading(col,'text'))+12
    user=ctypes.WinDLL('user32');user.GetDpiForWindow.argtypes=[ctypes.c_void_p];user.GetDpiForWindow.restype=ctypes.c_uint
    (tmp_path/'SCALING.json').write_text(json.dumps({'tk_scale':scale,'os_window_dpi':user.GetDpiForWindow(hwnd(app)),
         'geometry':app.geometry(),'scope':'process-local Tk scaling; no OS setting changed'}),encoding='utf-8')
