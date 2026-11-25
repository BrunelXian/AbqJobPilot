"""Fixed UI capability adapter shared by every supported Skin."""
from __future__ import annotations

from pathlib import Path


class GUIControllerError(RuntimeError):
    pass


class GUIControllerAdapter:
    """Narrow presentation API; never exposes clients, tokens, stores, or processes."""
    _ACTIONS = frozenset({"choose_project", "reconnect", "disconnect", "start_owner", "stop_owner", "open_agent"})

    def __init__(self, workspace):
        self.__workspace = workspace

    def snapshot(self) -> dict:
        workspace = self.__workspace
        project = getattr(workspace, "project", None)
        return {
            "project_name": getattr(workspace, "product_name", None) or (Path(project).name if project else None),
            "owner_state": getattr(workspace, "service_state", "NOT_SELECTED"),
            "connection_state": getattr(workspace, "connection_code", "NOT_RUNNING"),
            "run_count": len(getattr(workspace, "run_items", {})),
            "start_queue_available": False,
        }

    def perform(self, action: str) -> None:
        """Dispatch only fixed UI commands; payloads and arbitrary callbacks are forbidden."""
        if not isinstance(action, str) or action not in self._ACTIONS:
            if action == "start_queue":
                raise GUIControllerError("Start Queue is unavailable until a REAL backend is authorized")
            raise GUIControllerError("Unsupported GUI action")
        workspace = self.__workspace
        if action == "choose_project":
            workspace.choose_project()
        elif action == "reconnect":
            workspace.reconnect()
        elif action == "disconnect":
            workspace.disconnect()
        elif action in {"start_owner", "stop_owner"}:
            (workspace.start_service if action == "start_owner" else workspace.stop_service)()
        elif action == "open_agent":
            workspace.open_agent_command()
