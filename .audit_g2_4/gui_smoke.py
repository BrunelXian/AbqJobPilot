import sys,json,runpy,hashlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from abqjobpilot.gui_app import AbqJobPilotApp
from abqjobpilot.runner_core import QueueRunner
root=Path(r'D:\Projects\AbqJobPilotProjects\RL-LAM-ScanOPT-Stage1-3');repo=Path(__file__).resolve().parents[1]; result={}; errors=[]
original_init=AbqJobPilotApp.__init__
def init(app):
 original_init(app)
 def check():
  try:
   result['startup_header']=app.project_name_var.get();assert app.project_manager.current is None
   parent=app.nametowidget(app.menu_bar.entrycget(0,'menu'));recent=app.nametowidget(parent.entrycget(5,'menu'))
   labels=[recent.entrycget(i,'label') for i in range(recent.index('end')+1)]
   index=next(i for i,label in enumerate(labels) if 'RL-LAM-ScanOPT-Stage1-3' in label)
   result.update(recent_labels=labels,store=str(app.project_manager.recent_file),resolved_store=str(app.project_manager.recent_file.resolve()))
   recent.invoke(index)
   assert app.project_manager.current.root==root
   assert app.project_manager.current.project_id=='ed1a47a2-c3d6-4c2d-843a-b8942c66e828'
   assert not app.runner.is_running()
   result.update(open_header=app.project_name_var.get(),results_rows=len(app.results_tree.get_children()),runner_started=False)
  except BaseException as exc:errors.append(repr(exc))
  finally:app.after(300,app.destroy)
 app.after(400,check)
# Recent/menu/runtime behavior is real. Suppress unrelated history projection to keep canonical DB byte-identical.
with patch.object(AbqJobPilotApp,'__init__',init),patch.object(AbqJobPilotApp,'_read_gpu_text',return_value='--'),patch('abqjobpilot.gui_app.sync_history_from_runtime',return_value={}),patch.object(QueueRunner,'start',side_effect=AssertionError('Forbidden')),patch('subprocess.Popen',side_effect=AssertionError('Forbidden')):
 runpy.run_path(str(repo/'run_gui.py'),run_name='__main__')
result.update(errors=errors,history_projection_guard=True,real_tk_mainloop=True)
(repo/'.audit_g2_4'/('gui-launch-'+sys.argv[1]+'.json')).write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));assert not errors
