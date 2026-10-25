"""Experimental test-only execution service, not the legacy API or a Solver SDK."""

from .models import ConfigSnapshot, ExecutionError, ExecutionPlan, JobSpec, ProjectContext

__all__ = ["ConfigSnapshot", "ExecutionError", "ExecutionPlan", "JobSpec", "ProjectContext",
           "ExecutionService", "ExperimentStore", "create_experiment", "open_existing_read_only"]


def __getattr__(name):
    # A connect-only client must not load the writer/service just by importing this package.
    if name == "ExecutionService":
        from .service import ExecutionService
        return ExecutionService
    if name in {"ExperimentStore", "create_experiment", "open_existing_read_only"}:
        from .store import ExperimentStore, create_experiment, open_existing_read_only
        return {"ExperimentStore": ExperimentStore, "create_experiment": create_experiment,
                "open_existing_read_only": open_existing_read_only}[name]
    raise AttributeError(name)
