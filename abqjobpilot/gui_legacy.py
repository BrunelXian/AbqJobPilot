"""Legacy GUI dependencies, loaded only for the existing queue workspace."""
from . import config
from .app_metadata import STABLE_GITHUB_URL
from .command_console import AI_INSTRUCTION, CLI_EXAMPLES, AgentCommandConsole
from .gui_presentation import (SUCCESS_BACKGROUND, SUCCESS_FOREGROUND, filter_jobs,
                               read_log_tail, status_presentation)
from .gui_table_state import queue_display_jobs, result_display_jobs, restore_iids, row_iid, selected_job_id
from .queue_store import (
    add_folder_to_queue,
    add_inp_job_to_queue,
    apply_resources_to_queued_jobs,
    init_storage,
    load_queue,
    mark_job_skipped,
    move_queued_job,
    remove_queued_job,
    remove_queued_jobs,
    remove_result_job,
    remove_result_jobs,
    requeue_result_job,
)
from .api import AbqJobPilotClient, JobRequest
from .api.status_reader import expected_paths
from .project import ProjectInfo, ProjectManager, export_project_archive, import_legacy_runtime, import_project_archive
from .project.manager import default_projects_root, ensure_default_projects_root, set_default_projects_root
from .database import DatabaseFailure, ProjectHistoryRepository, sync_history_from_runtime
from .status_codes import normalize_status
from .runner_core import QueueRunner
from .recovery_dialog import RecoveryDialog
from .settings_store import load_settings, save_settings
from .utils import format_bytes, now_iso, open_folder, read_json, tail_text, write_json

