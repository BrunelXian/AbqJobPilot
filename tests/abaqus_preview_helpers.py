"""Synthetic INP strings only; files are materialized exclusively in pytest temp roots."""

PROJECT = {"project_id": "offline_project", "project_instance_id": "offline_instance"}
PROFILE = {"profile_id": "declared_2024", "profile_version": 1, "platform": "windows-local",
           "product": "Abaqus/Standard", "declared_version": "2024", "phase": "analysis",
           "cpus": 1, "gpus": 0, "memory_mb": 512, "wall_seconds": 60, "scratch_relative": "scratch"}
MODEL = """*HEADING
Restricted synthetic truss
*NODE
1,0,0,0
2,1,0,0
*ELEMENT, TYPE=T3D2, ELSET=BAR
1,1,2
*MATERIAL, NAME=STEEL
*ELASTIC
210000,0.3
*SOLID SECTION, ELSET=BAR, MATERIAL=STEEL
1.0
"""
STEP = """*STEP
*STATIC
0.1,1,1e-5,0.1
*BOUNDARY
1,1,3,0
2,2,3,0
*CLOAD
2,1,1
*END STEP
"""


def case(tmp_path, *, contents=None):
    root = tmp_path / "engineering"
    root.mkdir()
    (root / "source.inp").write_bytes((MODEL + STEP if contents is None else contents).encode("ascii"))
    return {"project": dict(PROJECT), "runtime_profile": dict(PROFILE), "engineering_root": str(root),
            "submission_cwd": str(root), "main_input": "source.inp", "job_name": "candidate"}
