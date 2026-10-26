"""Trusted local product bridge. No GUI/IPC caller imports or exposes issuance.

Like existing closeout.issue, this is an operator-program entry, not a remote
approval API. DPAPI establishes instance access only. The explicit, lock-held
authorize call records the actual independent approval; connection, lifecycle
and Solver tokens do not become recovery permissions. Same-user arbitrary shell
access remains trusted; this is not OS separation or a human approval platform.
"""
from .product_project import open_project
from .service_lifecycle import ServiceLifecycleManager
from .execution.recovery import RecoveryManagementSession


def open_product_recovery(project, run_id):
    open_project(project)
    manager = ServiceLifecycleManager(project)
    return RecoveryManagementSession(manager.context, manager._profile()['authority_instance'], run_id)
