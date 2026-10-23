"""Import audit in its own ordinary Python process."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[1] / 'controller'))
def guard(event, args):
    if event in {'subprocess.Popen','os.system','os.startfile','sqlite3.connect'}:
        raise AssertionError('Import spawned or opened database')
sys.addaudithook(guard)
import probe
print('IMPORT_NO_EXECUTION')
