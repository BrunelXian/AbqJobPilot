"""Read-only local command discovery; never probes licenses or executes Solver."""
import os,shutil
from pathlib import Path

def discover():
    candidates=[]
    explicit=os.environ.get('ABQJOBPILOT_ABAQUS_COMMAND')
    if explicit:candidates.append(('configured',explicit))
    found=shutil.which('abaqus') or shutil.which('abaqus.bat')
    if found:candidates.append(('PATH',found))
    for drive in ('C:','D:'):
        for base in ('SIMULIA/Commands','SIMULIA/EstProducts/Commands'):
            root=Path(drive+'/')/base
            if root.is_dir():
                candidates.extend(('installed_commands',str(p)) for p in sorted(root.glob('abq*.bat')))
    entries=[{'path':str(Path(p).absolute()),'source':source,'exists':Path(p).is_file()} for source,p in candidates]
    selected=next((e['path'] for e in entries if e['exists']),None)
    return {'solver_entry':selected,'entry_status':'FOUND' if selected else 'NOT_FOUND','candidates':entries,
            'environment_status':'NOT_VERIFIED','license_status':'NOT_VERIFIED',
            'execution_authorization':'NOT_GRANTED','solver_started':False}
