"""One fixed analysis, dispatched ONLY by ExecutionService's owner worker.

No registration by clients, automatic retries, result imports or termination.
Observation is bounded; unresolved membership permanently retains the slot.
"""
import os
from pathlib import Path
import subprocess
import time

from .models import ExecutionError, bytes_digest, canonical_json, identifier, now, require
from .paths import confined
from .standard_contract import BACKEND, CMD, ENTRY, INPUT_DIGEST, identity
from .standard_process import Observer, check_host, close_reference
from .standard_dat import parse


def write_new(path, value):
    with path.open('x',encoding='utf-8') as f:
        f.write(canonical_json(value)); f.flush(); os.fsync(f.fileno())


def call_data(context, plan, run):
    root=Path(plan['engineering']); output=Path(context.runtime_root)/'standard_runs'/run['run_id']
    command=f'"{CMD}" /d /s /c ""{ENTRY}" job={plan["job_name"]} input=axial_bar.inp analysis interactive cpus=1 gpus=0 memory="2048 mb" scratch="{plan["scratch"]}""'
    home=output/'home'; temp=output/'tmp'
    env={'SystemRoot':r'C:\Windows','WINDIR':r'C:\Windows','COMSPEC':CMD,
         'PATH':r'C:\Windows\System32;C:\Windows;C:\Windows\System32\Wbem',
         'PROCESSOR_ARCHITECTURE':'AMD64','SystemDrive':'C:', 'ProgramData':r'C:\ProgramData',
         'ProgramFiles':r'C:\Program Files','ProgramFiles(x86)':r'C:\Program Files (x86)','ProgramW6432':r'C:\Program Files',
         'HOME':str(home),'USERPROFILE':str(home),'HOMEDRIVE':home.drive,'HOMEPATH':str(home)[2:],
         'APPDATA':str(home/'AppData/Roaming'),'LOCALAPPDATA':str(home/'AppData/Local'),
         'TEMP':str(temp),'TMP':str(temp)}
    return {'command_line':command,'application':CMD,'cwd':str(root),'environment':env,'output':str(output)}


def _launch(call, out, err):
    # Only production creation seam; tests replace this function, never the command via IPC.
    return subprocess.Popen(call['command_line'],executable=call['application'],cwd=call['cwd'],env=call['environment'],
        stdin=subprocess.DEVNULL,stdout=out,stderr=err,shell=False,close_fds=True,creationflags=0x08000000)


def collect(context, plan, run, intent, process_view):
    result={'solver':'EVIDENCE_INSUFFICIENT','numerical':'EVIDENCE_INSUFFICIENT',
            'odb_content_validation':'NOT_RUN','source':'current_run_bounded_text_read','artifacts':[]}
    require(identity(Path(plan['engineering'])/'axial_bar.inp',65536)['digest']==INPUT_DIGEST,
            'PLAN_STALE','Input changed during execution')
    payloads={}
    for ext in ('dat','sta','msg','log'):
        path=confined(context.test_root,Path(plan['engineering'])/(plan['job_name']+'.'+ext))
        if not path.exists(): continue
        before=path.stat()
        require(before.st_ctime_ns >= intent['intent_at_ns'] and before.st_mtime_ns >= intent['intent_at_ns'],
                'EVIDENCE_IDENTITY_MISMATCH','Old or unassociated output rejected')
        require(before.st_size<=1048576,'LIMIT_EXCEEDED','Text evidence exceeds bound')
        raw=path.read_bytes(); after=path.stat()
        require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
                (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'EVIDENCE_CHANGED','Text changed while reading')
        payloads[ext]=raw
        result['artifacts'].append({'logical_ref':'output:'+ext,'digest':bytes_digest(raw),'size':len(raw),
            'device':before.st_dev,'inode':before.st_ino,'mtime_ns':before.st_mtime_ns,'read_at':now()})
    if not process_view.get('all_observed_exited'):
        result['reason']='OBSERVED_EXIT_INCOMPLETE'; return result
    if 'dat' not in payloads:
        result['reason']='DAT_MISSING'; return result
    parsed=parse(payloads['dat']); result.update({k:v for k,v in parsed.items() if k not in ('scope','schema')})
    # DAT complete footer, STA completion and MSG convergence are independent
    # text evidence, never a substitute for full process-set exit verification.
    sta=payloads.get('sta',b'').decode('cp936',errors='strict')
    msg=payloads.get('msg',b'').decode('cp936',errors='strict')
    if b'***ERROR' in b'\n'.join(payloads.values()) or 'HAS NOT BEEN COMPLETED' in sta:
        result['solver']='FAILED_TEXT_EVIDENCE'
    elif parsed['solver']=='DAT_COMPLETION_TEXT_OBSERVED' and 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY' in sta and 'THE ANALYSIS HAS BEEN COMPLETED' in msg:
        result['solver']='COMPLETED_TEXT_EVIDENCE'
    else: result['solver']='EVIDENCE_INSUFFICIENT'
    result['validation_policy']='fixed-2024-axial-dat-v1'
    return result


class StandardBackend:
    def __init__(self,config): self.config=config

    def execute(self,context,plan,run,record,checkpoint,authorize_start):
        # Every admission happens in the actual owner process, before the
        # external call. A prior GUI/check result is never used as admission.
        authorize_start(); host=check_host(self.config)
        require(host['eligible'],'HOST_UNVERIFIED','Service host contract not satisfied')
        call=call_data(context,plan,run)
        output=confined(context.test_root,call['output']); output.mkdir(parents=True,exist_ok=False)
        for name in ('home/AppData/Roaming','home/AppData/Local','tmp'): (output/name).mkdir(parents=True,exist_ok=True)
        intent={'run_id':run['run_id'],'plan_digest':plan['plan_digest'],'phase_attempt_id':run['phase_attempt_id'],
            'project_instance_id':context.project_instance_id,'output_key':plan['output_key'],
            'owner_id':run['owner_id'],'intent_at_ns':time.time_ns(),'state':'START_INTENT'}
        attempt=confined(context.test_root,Path(plan['engineering'])/('.'+plan['job_name']+'.intent.json'))
        write_new(attempt,intent)  # O_EXCL + flush/fsync, never reset even on partial failure.
        record('STANDARD_LAUNCH_INTENT',launch_state='INTENT_PERSISTED',host_observation=host,
               launch_intent=intent,member_completeness='UNKNOWN',overall_exit='UNKNOWN')
        checkpoint('standard:after_intent')
        require(not list(Path(plan['engineering']).glob(plan['job_name']+'.*')),'OUTPUT_CONFLICT','Output appeared after claim')
        authorize_start(started=True)
        require(check_host(self.config)['eligible'],'HOST_UNVERIFIED','Service host changed before creation')
        child=observer=None
        try:
            with (output/'stdout.bin').open('xb',buffering=0) as out, (output/'stderr.bin').open('xb',buffering=0) as err:
                record('STANDARD_CREATE_ENTERING',launch_state='CALL_ENTERED_OUTCOME_UNKNOWN')
                begin=time.monotonic(); checkpoint('standard:before_create')
                child=_launch(call,out,err)  # Exactly one call; no exception replay.
                creation_ms=int((time.monotonic()-begin)*1000)
                checkpoint('standard:after_create')
                record('STANDARD_CREATED',launch_state='PROCESS_OBJECT_RETURNED',creation_duration_ms=creation_ms,execution_phase='OBSERVING')
                observer=Observer(child); previous=None
                deadline=time.monotonic()+plan['resources']['observation_seconds']
                while True:
                    view=observer.sample()
                    if view!=previous:
                        record('STANDARD_PROCESS_OBSERVATION',process_observation='OBSERVED_SUBSET',**view)
                        previous=view
                    if time.monotonic()>=deadline: break
                    time.sleep(min(.1,max(0,deadline-time.monotonic())))
                record('STANDARD_OBSERVATION_ENDED',observation_deadline_reached=True,
                       observation_ended_at=now(),execution='VALIDATING',execution_phase='OBSERVATION_ENDED')
                checkpoint('standard:before_validation')
                try: result=collect(context,plan,run,intent,view)
                except (ExecutionError,OSError,UnicodeError) as exc:
                    result={'solver':'EVIDENCE_INSUFFICIENT','numerical':'EVIDENCE_INSUFFICIENT',
                        'odb_content_validation':'NOT_RUN','reason':exc.code if isinstance(exc,ExecutionError) else 'TEXT_READ_FAILED',
                        'artifacts':[]}
                return result
        finally:
            if observer is not None: observer.close()
            if child is not None: close_reference(child)


def persist_result(service,run_id,result):
    from .store import document,update_run
    store=service.store
    with store.transaction('standard_result') as conn:
        run=document(conn,'runs','run_id',run_id)
        obs={'observation_id':identifier('obs'),'run_id':run_id,'phase_attempt_id':run['phase_attempt_id'],
             'kind':'STANDARD_TEXT','observed_at':now(),'artifacts':result.get('artifacts',[])}
        verdict={'PRIMARY_THREE_PASS':'PASS','NUMERICAL_FAIL':'FAIL'}.get(result['numerical'],'UNKNOWN')
        val={'validation_id':identifier('val'),'run_id':run_id,'phase_attempt_id':run['phase_attempt_id'],
             'scope':'fixed_standard_dat_only','policy_id':'fixed-2024-axial-dat-v1','policy_version':1,
             'validator_id':'standard-dat-validator','validator_version':1,'verdict':verdict,'recorded_at':now(),
             'evidence_refs':[obs['observation_id']],'details':result}
        conn.execute('INSERT INTO observations VALUES(?,?,?)',(obs['observation_id'],run_id,canonical_json(obs)))
        conn.execute('INSERT INTO validations VALUES(?,?,?)',(val['validation_id'],run_id,canonical_json(val)))
        update_run(conn,run,'STANDARD_RESULT_RECORDED',execution='BLOCKED',reconciliation='RECONCILIATION_REQUIRED',
            execution_phase='EVIDENCE_RECORDED',
            solver_conclusion=result['solver'],numerical_validation=result['numerical'],odb_content_validation='NOT_RUN',
            artifact_validation={'PASS':'VALID','FAIL':'INVALID','UNKNOWN':'UNKNOWN'}[verdict],
            validation_scope='fixed_standard_dat_only',backend_outcome='UNKNOWN',
            result_reason=result.get('reason'),evidence_refs=[obs['observation_id'],val['validation_id']])
        # No slot release: observed-subset exits cannot establish complete closure.
    store.pause_after_error()


def progress(store,context,run_id,after_sequence,limit):
    """Bounded latest text projection; no raw environment/license/errors are exported."""
    from .models import integer
    from .store import document
    integer(after_sequence); integer(limit,1); require(limit<=64,'LIMIT_EXCEEDED','Log page limit')
    with store.read() as conn:
        run=document(conn,'runs','run_id',run_id); plan=document(conn,'plans','plan_id',run['plan_id'])
    rows=[]
    for ext in ('sta','msg','log'):
        path=confined(context.test_root,Path(plan['engineering'])/(plan['job_name']+'.'+ext))
        if not path.exists(): continue
        with path.open('rb') as f: raw=f.read(1048577)
        require(len(raw)<=1048576,'LIMIT_EXCEEDED','Log byte limit')
        # Byte counts and exact known markers are useful live progress without
        # exporting arbitrary installation, credential or command text.
        rows.append({'event':ext.upper()+'_BYTES','bytes':len(raw),'observed_at':now()})
        for marker in (b'THE ANALYSIS HAS COMPLETED SUCCESSFULLY',b'THE ANALYSIS HAS BEEN COMPLETED',b'***ERROR'):
            if marker in raw: rows.append({'event':marker.decode('ascii'),'source':ext,'observed_at':now()})
    require(len(rows)<=limit,'LIMIT_EXCEEDED','Latest log view exceeds requested record bound')
    return {'source':'bounded_standard_text_latest','records':rows,'next_sequence':0,
            'has_more':False,'read_at':now(),'status':'RECORDED' if rows else 'NOT_RECORDED'}
