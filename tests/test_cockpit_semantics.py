"""Final display semantics; core evidence is immutable and never interpreted as success."""
import json
import pytest
from abqjobpilot.cockpit_display import short_identity,short_observed,progress_title
from test_native_workspace import desktop

@pytest.mark.parametrize('source,key',[
 ('fixed_worker_self_report_not_exit_or_validation','workerLog'),
 ('bounded_standard_text_latest','staSummary'),(None,'progressUnavailable'),('future_source','progressUnavailable')])
def test_log_source_not_guessed_from_backend_or_file_presence(source,key):
    assert progress_title(source)==key


def test_long_identity_and_time_are_display_only():
    rid='r_'+'0123456789abcdef'*2
    assert short_identity(rid)==rid[:12]+'…'+rid[-8:]
    assert short_identity('short')=='short'
    assert short_observed('2026-10-26T12:01:02.999999+08:00')=='2026-10-26 12:01:02+08:00'
    assert short_observed('—')=='—'


def test_live_and_unresolved_results_remain_visible_and_raw_evidence_unchanged(desktop):
    app,w=desktop
    # Display-only contract fixture; Windows tests supply actual service evidence.
    rid='r_'+'a'*32
    run={'run_id':rid,'plan_id':'plan','backend_id':'python-process-fixture-v1','job_id':'job','execution':'START_INTENT',
         'solver_conclusion':'NOT_RUN','artifact_validation':'NOT_RUN','exit_verification':'PARTIAL',
         'process_exits':[{'role':'launcher','exit_code':0}],'managed_completion':'NOT_CONFIRMED','revision':12}
    row={**run,'receipt':{'run_id':rid,'request_id':'request'}}
    data={'connected':True,'observed_at':'2026-10-26T12:01:02.999+08:00','endpoint':{'project_id':'p','project_instance_id':'i','owner_id':'owner'},
          'run':run,'receipt':row['receipt'],'gate':{'state':'PAUSED'},'validations':[],
          'progress':[{'event':'WAITING','sequence':3}],'events':[{'type':'PROCESS_EXIT_OBSERVED'}],
          'project_page':{'runs':[row],'slot_run_id':rid,'next_before_row':None},
          'progress_source':'fixed_worker_self_report_not_exit_or_validation'}
    before=json.dumps(data,sort_keys=True);w._render(data);app.update()
    assert w.results_tree.item(rid,'values')[1:4]==('START_INTENT','NOT_RUN','NOT_RUN')
    assert 'not scope completion' in w.current_dimensions.get()
    assert w.log_titles['progress'].cget('text')=='Worker Log · self-report'
    assert rid in w.detail_boxes['identity'].get('1.0','end') and rid not in w.current_summary.get()
    assert data['observed_at'] in w.detail_boxes['identity'].get('1.0','end')
    assert json.dumps(data,sort_keys=True)==before
    w.filters[w.results_tree].set(rid);assert w.results_tree.get_children()==(rid,)
    w._render({'connected':False,'code':'COMMUNICATION_UNKNOWN'})
    assert not w.connected and 'last successful' in w.status.get()
    assert 'WAITING' in w.log_widgets['progress'].get('1.0','end')
    row['execution']='UNKNOWN';w.refresh_tables();assert w.results_tree.item(rid,'values')[1]=='UNKNOWN'
    for locale in ('zh-CN','fr-FR','de-DE','en'):
        w.change_language(locale)
        assert w.results_tree.column('run','minwidth')>=170
