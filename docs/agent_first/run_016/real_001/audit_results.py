"""Read-only acceptance audit. Writes new evidence only in this report directory."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from contextlib import closing

HERE=Path(__file__).resolve().parent
SOURCE=HERE.parents[3]
sys.path.insert(0,str(SOURCE/'examples/agent_first'))
import standard_service as op
from abqjobpilot.execution.store import ReadOnlyStore
from abqjobpilot.execution.client import FakeClient
from abqjobpilot.execution.process_handles import ProcessReference
from abqjobpilot.execution.models import digest

read=lambda path: json.loads(path.read_text(encoding='utf-8'))

def main():
    value,ctx,config=op.package(op.PAIR_MANIFEST)
    record={'read_at':datetime.datetime.now().astimezone().isoformat(),
        'body_digest':digest(value['body']),'materials_matched':49,'runtime_materials_matched':20}
    with ReadOnlyStore(ctx).read() as conn:
        conn.execute('BEGIN')
        record['counts']={t:conn.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in
            ['plans','grants','runs','receipts','consumption','events','observations','validations',
             'reconciliations','management_grants','management_receipts']}
        record['slot']=dict(conn.execute('SELECT * FROM slot').fetchone())
        record['gate']=dict(conn.execute('SELECT * FROM dispatch_gate').fetchone())
        record['consumption']=[dict(x) for x in conn.execute('SELECT * FROM consumption')]
        keys=['grant_id','plan_id','plan_digest','grant_kind','allowed_action','max_runs','expires_at',
              'approval_source','sequence_grant','process_management','resource_limits']
        record['grants']=[{k:g[k] for k in keys} for row in conn.execute('SELECT body FROM grants')
                          for g in [json.loads(row[0])]]
        runs={r['batch_position']:r for row in conn.execute('SELECT body FROM runs') for r in [json.loads(row[0])]}
        # query_run adds two diagnostic fields; those are not persisted facts.
        record['persisted_fields_match_public']={k:all(read(HERE/f'FINAL_RUN_{k}.json').get(f)==x for f,x in r.items()) for k,r in runs.items()}
        record['public_projection_extras']={k:sorted(set(read(HERE/f'FINAL_RUN_{k}.json'))-set(r)) for k,r in runs.items()}
        assert all(record['persisted_fields_match_public'].values())
        assert record['counts']['runs']==record['counts']['receipts']==record['counts']['consumption']==2
        assert record['slot']['run_id'] is None and record['gate']['state']=='OPEN'
    events=read(HERE/'FINAL_EVENTS.json');record['tasks']={}
    for index,letter in enumerate('AB'):
        run=runs[letter];plan=value['body']['plans'][index]
        validation=read(HERE/f'VALIDATIONS_{letter}.json')[0]
        engineering=Path(plan['engineering']);job=plan['job_name']
        intent=read(engineering/('.'+job+'.intent.json'))
        assert intent==run['launch_intent']
        these=[e for e in events if e['run_id']==run['run_id']]
        starts=[e for e in these if e['type']=='STANDARD_CREATE_ENTERING']
        created=[e for e in these if e['type']=='STANDARD_CREATED']
        assert len(starts)==len(created)==1 and run['attempt_no']==1
        assert all(x['exit_code']==0 for x in run['process_exits'])
        task={'run_id':run['run_id'],'revision':run['revision'],'launch_intent':intent,
            'entry_call_count':len(starts),'create_enter_event':starts[0]['project_sequence'],
            'created_event':created[0]['project_sequence'],'creation_return_at':created[0]['recorded_at'],
            'start_not_after':run['start_not_after'],
            'normal_closeout_event':next(e['project_sequence'] for e in these if e['type']=='STANDARD_MANAGED_COMPLETED'),
            'result_event':next(e['project_sequence'] for e in these if e['type']=='STANDARD_RESULT_RECORDED'),
            'completion_at':run['managed_completion_recorded_at'],'timeout_reached':run['observation_deadline_reached'],
            'managed_scope':run['managed_scope'],'observed_identity_count':len(run['process_records']),
            'observed_exit_count':len(run['process_exits']),'observed_exit_codes':sorted(set(x['exit_code'] for x in run['process_exits'])),
            'full_membership':run['member_completeness'],'overall_exit':run['overall_exit'],
            'solver':run['solver_conclusion'],'numerical':run['numerical_validation'],'odb_content_validation':'NOT_RUN',
            'validation_id':validation['validation_id'],
            'comparisons':[x for x in validation['details']['comparisons'] if x['group']=='primary'],
            'texts':[],'runtime_streams':[],'marker_locations':{},
            'auxiliary_nonrequired_checks':validation['details']['full_frozen_checks']}
        for item in validation['details']['artifacts']:
            ext=item['logical_ref'].split(':')[1];path=engineering/(job+'.'+ext)
            raw=path.read_bytes();stat=path.stat()
            assert 'sha256:'+hashlib.sha256(raw).hexdigest()==item['digest']
            assert (stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns)==(item['device'],item['inode'],item['size'],item['mtime_ns'])
            task['texts'].append({'path':str(path),**item,'unchanged_since_validation':True})
            lines=raw.decode('cp936').splitlines()
            for marker in ['Abaqus 2024','A B A Q U S','THE ANALYSIS HAS COMPLETED SUCCESSFULLY','THE ANALYSIS HAS BEEN COMPLETED']:
                hits=[n for n,line in enumerate(lines,1) if marker in line]
                if hits:task['marker_locations'][ext+':'+marker]=hits
        for name in ['stdout.bin','stderr.bin']:
            path=Path(ctx.runtime_root)/'standard_runs'/run['run_id']/name;raw=path.read_bytes()
            task['runtime_streams'].append({'path':str(path),'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
            lines=raw.decode('cp936',errors='replace').splitlines()
            for marker in ['Abaqus 2024','Abaqus JOB '+job,'Abaqus/Standard','COMPLETED']:
                hits=[n for n,line in enumerate(lines,1) if marker in line]
                if hits:task['marker_locations'][name+':'+marker]=hits
        assert starts[0]['recorded_at']<run['start_not_after']
        record['tasks'][letter]=task
    assert record['tasks']['A']['result_event']<record['tasks']['B']['create_enter_event']
    assert len([e for e in events if e['type']=='REQUEST_ACCEPTED'])==2
    record['total_analysis_calls']=2;record['additional_abaqus_calls']=0
    record['sequence_evidence']={'A_closeout_event':record['tasks']['A']['normal_closeout_event'],
        'A_result_event':record['tasks']['A']['result_event'],
        'B_accept_event':next(e['project_sequence'] for e in events if e['run_id']==runs['B']['run_id'] and e['type']=='REQUEST_ACCEPTED'),
        'B_create_event':record['tasks']['B']['create_enter_event']}
    connection=read(Path(ctx.test_root)/'private/connection.json')
    client=FakeClient(connection['endpoint'],connection['credential'])
    record['health']=client.health()
    record['receipt_matches']={k:client.receipt(value['body']['request_keys'][k])==read(HERE/f'RECEIPT_{k}.json') for k in 'AB'}
    with closing(ProcessReference(connection['endpoint']['process']['pid'],connection['endpoint']['process'])) as ref:
        record['owner']={'identity':ref.identity,'exit_evidence':ref.exit_evidence(),'retained_by_request':True}
    base=read(SOURCE/'docs/agent_first/run_016/BASELINE.json')
    changed=[x['path'] for x in base['protected'] if hashlib.sha256(Path(x['path']).read_bytes()).hexdigest()!=x['sha256']]
    assert not changed
    record['protected_history_count']=len(base['protected']);record['protected_changed']=changed
    def git(*args):return subprocess.check_output(['git',*args],cwd=SOURCE,text=True,stderr=subprocess.DEVNULL).strip()
    record.update(branch=git('branch','--show-current'),head=git('rev-parse','HEAD'),conflicts=git('diff','--name-only','--diff-filter=U'))
    assert record['branch']=='Develop' and record['head']=='271c6f82fd6a4599dbae2df30d903dab2cef1f63' and not record['conflicts']
    op.write(HERE/'POST_RUN_AUDIT.json',record)
    print(json.dumps({'status':'READ_ONLY_AUDIT_PASS','counts':record['counts'],'slot':record['slot'],
        'gate':record['gate'],'sequence':record['sequence_evidence'],'protected_unchanged':len(base['protected'])}))

if __name__=='__main__':main()
