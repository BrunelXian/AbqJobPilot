"""Cockpit selection uses actual isolated fixed-Python service records, never demo rows."""
import json
from pathlib import Path
from test_native_workspace_windows import NativeGui,choose,save
from test_attachment_gui import action
from test_service_attachment import connection
from test_managed_scope import managed,terminal,bind,directory
from supervisor_helpers import wait_until,read_json


def test_two_real_runs_selection_drives_summary_logs_evidence(tmp_path):
    gui=None;private=None
    with managed(tmp_path,['normal','result_wait']) as h:
        try:
            owner=h.owner();client=h.client()
            first=client.submit(h.requests[0])['receipt'];a=first['run_id'];terminal(h,a)
            second=client.submit(h.requests[1])['receipt'];b=second['run_id'];worker=bind(h,b,'worker')
            wait_until(lambda:len(client.run(b)['process_exits'])>=2)
            private=connection(h);gui=NativeGui(tmp_path,'selection_gui');choose(gui,h,b)
            busy=gui.view(lambda v:'WAITING' in v['progress_text'])
            actual=client.run(b)
            assert actual['execution']=='START_INTENT' and actual['exit_verification']=='PARTIAL'
            assert actual['managed_scope']['active_processes']>0 and len(actual['process_exits'])>=2
            assert 'PROCESS_EXIT_OBSERVED' in busy['event_text']
            assert busy['log_titles']['progress']=='Worker Log · self-report'
            assert busy['log_titles']['events']=='Events · execution service'
            assert any(row[1]=='START_INTENT' and row[2]=='NOT_RUN' for row in busy['results_rows'])
            assert 'not scope completion' in busy['current_dimensions']
            action(gui,'select_results',run_id=a)
            history=gui.view(lambda v:v['run_id']==a and a in v['details']['identity'])
            assert 'WAITING' not in history['progress_text']
            assert 'COMMITTED_EMPTY_SCOPE' in history['details']['identity']
            assert 'FINISHED' in history['details']['identity']
            for rid in (b,a,b):action(gui,'select',run_id=rid)
            active=gui.view(lambda v:v['run_id']==b and b in v['details']['identity'] and 'WAITING' in v['progress_text'])
            assert a not in active['details']['identity']
            action(gui,'size',geometry='1600x900+0+0');action(gui,'capture',name='linked_run')
            assert client.receipt('key-0')==first and client.receipt('key-1')==second
            assert len(read_json(owner.control/'physical-launches.json'))==2
            assert worker.exit_evidence() is None
            save(tmp_path,'SELECTION_EVIDENCE',{'first':first,'second':second,'history':history,'active':active,'partial_run_at_observation':actual,'owner':owner.identity,'calls':2,'abaqus_calls':0})
            gui.normal_close();(directory(h,b)/'release.json').write_text('{}',encoding='utf-8');terminal(h,b)
        finally:
            if gui:gui.close()
            if private and private.exists():private.unlink()
