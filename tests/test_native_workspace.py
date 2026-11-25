"""Native Tk display tests, explicit temporary Runtime/Recent/preferences only."""
import json
import hashlib
import time
import sys
import os
from pathlib import Path
from string import Formatter
from unittest.mock import patch
import pytest
from abqjobpilot.ui_resources import LANGUAGES, catalog, translate, DisplayPreferences
from abqjobpilot.gui_app import AbqJobPilotApp

_tcl=Path(sys.base_prefix)/'tcl'/'tcl8.6';_tk=Path(sys.base_prefix)/'tcl'/'tk8.6'
if not Path(os.environ.get('TCL_LIBRARY','')).joinpath('init.tcl').is_file():os.environ['TCL_LIBRARY']=str(_tcl)
if not Path(os.environ.get('TK_LIBRARY','')).joinpath('tk.tcl').is_file():os.environ['TK_LIBRARY']=str(_tk)


@pytest.fixture
def desktop(tmp_path,monkeypatch,request):
    monkeypatch.setattr('abqjobpilot.abaqus_environments.discover',lambda:[])
    monkeypatch.setenv('ABQJOBPILOT_UI_PREFS',str(tmp_path/'display.json'))
    monkeypatch.setenv('APPDATA',str(tmp_path/'appdata'))
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
    for key in (key for key in w.pages if key!='classic'):
        w.navigate(key);app.update();assert w.current_page==key
        assert w.pages[key].winfo_ismapped()
    before=len(w.lifecycle_threads);w.legacy();assert w.status.get()==w.t('classicUnavailable')
    assert len(w.lifecycle_threads)==before
    assert w.reader is None and w.classic_pane is None
    assert not list(tmp_path.rglob('execution.sqlite3'))
    assert not list(tmp_path.rglob('queue.json'))
    assert not list(tmp_path.rglob('connection.json'))


@pytest.mark.parametrize('locale',list(LANGUAGES))
def test_catalog_complete_parameters_and_native_language(tmp_path,locale):
    en=catalog('en');other=catalog(locale);assert en.keys()==other.keys()
    fields=lambda v:{field for _,field,_,_ in Formatter().parse(v) if field}
    for key in en:assert fields(en[key])==fields(other[key]),key
    preferences=DisplayPreferences(tmp_path/'display.json');preferences.save(language=locale)
    assert DisplayPreferences(preferences.path).data['language']==locale
    assert translate(locale,'no_such_key')!= 'no_such_key'
    assert translate(locale,'observed',time='12:00').endswith('12:00')


def test_locale_fallback_is_display_only(tmp_path):
    p=tmp_path/'prefs.json';p.write_text('{"language":"unsupported"}',encoding='utf-8')
    preferences=DisplayPreferences(p);assert preferences.data['language']=='en'
    preferences.save(language='de-DE',grant='forbidden',dispatch='OPEN')
    assert 'grant' not in p.read_text() and 'dispatch' not in p.read_text()
    assert translate('invalid','open')=='Open Project'


def test_disabled_classic_notice_is_non_modal_and_has_no_effects(desktop,tmp_path):
    app,w=desktop
    with patch('tkinter.messagebox.showwarning') as warning, patch('tkinter.messagebox.showerror') as error:
        w.navigate('classic');w.legacy();app.update()
        assert not warning.called and not error.called
    assert w.current_page=='overview' and w.status.get()==w.t('classicUnavailable')
    assert w.reader is None and w.lifecycle_threads==[] and w.classic_pane is None


def test_queue_results_use_job_fields_and_explicit_unavailable_values(desktop):
    app,w=desktop
    run={'run_id':'run_0123456789abcdef','job_id':'job_fixture','job_name':'Axial Fixture',
         'execution':'UNKNOWN','execution_phase':'RECONCILIATION_REQUIRED','backend_id':'python-process-fixture-v1',
         'created_at':'2026-11-13T09:00:00Z','solver_conclusion':'NOT_RUN','artifact_validation':'BLOCKED',
         'reconciliation':'REQUIRED','receipt':{'request_id':'req_0123456789abcdef'}}
    w.run_items={run['run_id']:run};w.refresh_tables();app.update()
    q=w.queue_tree.item(run['job_id'],'values');r=w.results_tree.item(run['job_id'],'values')
    assert q==('1','UNKNOWN','Axial Fixture',w.t('unavailable'),w.t('unavailable'),w.t('unavailable'),w.t('unavailable'))
    assert r==('UNKNOWN','Axial Fixture',w.t('unavailable'),w.t('unavailable'),w.t('unavailable'),w.t('unavailable'),w.t('unavailable'))
    w.filters[w.queue_tree].set('unknown');app.update()
    assert w.queue_tree.get_children()==(run['job_id'],)
    w.filters[w.queue_tree].set('missing');app.update()
    assert w.queue_tree.get_children()==()
    w.open_table_filter('queue');app.update()
    assert w.filter_windows['queue'].winfo_exists()
    w.filter_windows['queue'].destroy();app.update()


def test_agent_command_is_separate_read_only_and_not_service_authority(desktop):
    app,w=desktop
    w.open_agent_command();app.update()
    console=w.agent_console
    assert console.winfo_exists() and console.on_queue_changed is None
    denied=console.session.execute('enqueue --inp C:\\fixture.inp')
    assert denied['status']=='NOT_AVAILABLE_IN_NATIVE_GUI' and not denied['queue_changed']
    assert console.session.execute('help')['status']=='HELP'
    assert not hasattr(console.session,'operator_token')
    console.destroy();app.update()


def test_job_projection_statuses_attempts_sort_filter_and_evidence_inspector(desktop):
    """Synthetic TEST_ONLY display fixture; no Project Store or execution is touched."""
    app,w=desktop
    records=[
        {'run_id':'run_queue_old','job_id':'job_multi','job_name':'Multi Attempt','attempt_no':1,'execution':'FAILED','created_at':'2026-11-13T07:00:00Z'},
        {'run_id':'run_queue_new','job_id':'job_multi','job_name':'Multi Attempt','attempt_no':2,'execution':'QUEUED','created_at':'2026-11-13T08:00:00Z'},
        {'run_id':'run_success','job_id':'job_success','job_name':'Good','execution':'COMPLETED','created_at':'2026-11-13T09:00:00Z'},
        {'run_id':'run_failed','job_id':'job_failed','job_name':'Bad','execution':'FAILED'},
        {'run_id':'run_paused','job_id':'job_paused','job_name':'Paused','execution':'PAUSED'},
        {'run_id':'run_unknown','job_id':'job_unknown','job_name':'Unknown','execution':'UNKNOWN'},
        {'run_id':'run_blocked','job_id':'job_blocked','job_name':'Blocked','execution':'BLOCKED'},
    ]
    w.run_items={r['run_id']:r for r in records};w.refresh_tables();app.update()
    assert 'job_multi' in w.queue_tree.get_children() and 'job_multi' in w.results_tree.get_children()
    assert w.queue_tree.item('job_multi','values')[1]=='QUEUED'
    assert w.results_tree.item('job_multi','values')[0]=='FAILED'
    for status in ('COMPLETED','FAILED','UNKNOWN','PAUSED','BLOCKED'):
        assert any(w.results_tree.item(i,'values')[0]==status for i in w.results_tree.get_children())
    row=w.results_tree.item('job_success','values')
    assert row[4:]==(w.t('unavailable'),)*3
    w.sort_table(w.results_tree,0);assert w.results_tree.get_children()
    w.filters[w.results_tree].set('Bad');app.update();assert w.results_tree.get_children()==('job_failed',)
    w.filters[w.results_tree].set('')
    w.results_tree.selection_set('job_multi');w.results_tree.event_generate('<<TreeviewSelect>>');app.update()
    assert w.selected_run_id=='run_queue_old'
    assert w.current_page=='overview' and w.details.index(w.details.select())==1
    assert w.reader is None and w.lifecycle_threads==[]


def test_service_start_stop_confirmation_cancel_and_confirm(desktop):
    app,w=desktop;w.project='explicit-test-project';calls=[]
    w.lifecycle_action=lambda operation:calls.append(operation)
    with patch('abqjobpilot.desktop_workspace.messagebox.askyesno',return_value=False) as ask:
        w.start_service();w.stop_service()
        assert ask.call_count==2 and calls==[]
    with patch('abqjobpilot.desktop_workspace.messagebox.askyesno',return_value=True) as ask:
        w.start_service();w.stop_service()
        assert ask.call_count==2 and calls==['start','stop']


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


def test_language_switch_keeps_execution_identifiers_and_evidence_verbatim(desktop):
    app,w=desktop
    run={'run_id':'r_0123456789abcdef0123456789abcdef','job_id':'job_0123456789abcdef',
         'plan_id':'plan_0123456789abcdef','backend_id':'python-process-fixture-v1',
         'revision':4,'attempt_no':1,'execution':'UNKNOWN','execution_phase':'RECONCILIATION_REQUIRED',
         'solver_conclusion':'NOT_RUN','artifact_validation':'BLOCKED','reconciliation':'REQUIRED',
         'managed_scope':{'status':'NOT_CONFIRMED','input':'D:/fixture/model.inp',
                          'odb':'D:/fixture/model.odb','sta':'D:/fixture/model.sta','members':[]},'process_exits':[]}
    value={'connected':True,'observed_at':'2026-11-13T00:00:00Z',
        'endpoint':{'project_id':'project_0123456789abcdef','project_instance_id':'instance_0123456789abcdef','owner_id':'owner_0123456789abcdef'},
        'owner_process':{'pid':456,'creation_time_100ns':123456},'run':run,
        'receipt':{'request_id':'receipt_0123456789abcdef','run_id':run['run_id']},
        'gate':{'state':'PAUSED'},'slot_run_id':None,'project_page':{'runs':[run],'slot_run_id':None,'next_before_row':None},
        'validations':[{'validation_id':'validation_0123456789abcdef','verdict':'BLOCKED'}],
        'progress':[],'events':[],'log_error':None,'progress_source':None,'closeout':None,
        'interruption':None,'recovery':None,'job_name':'Job Fixture'}
    before=json.dumps(value,sort_keys=True)
    w._render(value)
    for locale in LANGUAGES:
        w.change_language(locale)
        assert json.dumps(value,sort_keys=True)==before
        evidence=w.detail_boxes['identity'].get('1.0','end')+w.detail_boxes['evidence'].get('1.0','end')
        assert run['run_id'] in evidence and run['plan_id'] in evidence
        assert 'UNKNOWN' in evidence and 'RECONCILIATION_REQUIRED' in evidence and 'BLOCKED' in evidence
        assert all(extension in evidence for extension in ('.inp','.odb','.sta'))


@pytest.mark.parametrize('scale',[1.0,1.25,1.5])
def test_native_sizes_and_local_scaling(desktop,scale,tmp_path):
    app,w=desktop
    app.tk.call('tk','scaling',96/72*scale)
    app.geometry('1366x768');w.change_language('de-DE');app.update()
    for key in w.pages:
        if key=='classic':continue
        w.navigate(key);app.update()
        assert w.command_button.winfo_rootx()+w.command_button.winfo_width()<app.winfo_rootx()+app.winfo_width()
        assert w.start_queue_button.winfo_rootx()+w.start_queue_button.winfo_width()<app.winfo_rootx()+app.winfo_width()
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


def test_language_switch_refreshes_empty_hints_without_losing_display_state(desktop):
    app,w=desktop
    # Selected display state only; no Owner, Store or execution connection.
    w.project='display-fixture-project';w.selected_run_id='run_fixture';w.selected_job_id='job_fixture'
    w.filters[w.queue_tree].set('queued');w.filters[w.results_tree].set('finished')
    w.last_view=None
    for locale in ('en','zh-CN','ja-JP','fr-FR','de-DE'):
        w.change_language(locale);app.update_idletasks()
        assert w.log_widgets['progress'].get('1.0','end-1c')==w.t('noProgress')
        assert w.log_widgets['events'].get('1.0','end-1c')==w.t('noEvents')
        assert all(box.get('1.0','end-1c')==w.t('chooseRun') for box in (*w.detail_boxes.values(),w.result_box))
        assert w.project=='display-fixture-project' and w.selected_run_id=='run_fixture'
        assert w.selected_job_id=='job_fixture'
        assert w.filters[w.queue_tree].get()=='queued' and w.filters[w.results_tree].get()=='finished'
    assert w.reader is None and w.lifecycle_threads==[]

def test_classic_refusal_is_accurate_in_all_locales():
    from abqjobpilot.ui_resources import catalog
    for locale in ('en','zh-CN','ja-JP','fr-FR','de-DE'):
        message=catalog(locale)['classicUnavailable']
        assert 'Frozen' in message
        assert 'Job' in message
        assert any(word in message.lower() for word in ('unavailable','不提供','利用できません','propose pas','keinen alten'))
        assert 'TEST_ONLY' in message
