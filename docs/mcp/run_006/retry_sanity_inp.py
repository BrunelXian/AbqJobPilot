"""Generate and statically check the disposable Run 006 one-element INP.

This does not call Abaqus or perform a solver datacheck.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path


INP = """*Heading
Run 006 disposable C3D8 lineage sanity model; units mm, MPa
*Node
1, 0., 0., 0.
2, 1., 0., 0.
3, 1., 1., 0.
4, 0., 1., 0.
5, 0., 0., 1.
6, 1., 0., 1.
7, 1., 1., 1.
8, 0., 1., 1.
*Element, type=C3D8, elset=EALL
1, 1, 2, 3, 4, 5, 6, 7, 8
*Nset, nset=BASE
1, 2, 3, 4
*Nset, nset=TOP
5, 6, 7, 8
*Material, name=STEEL
*Elastic
210000., 0.3
*Solid Section, elset=EALL, material=STEEL
,
*Step, name=STATIC, nlgeom=NO
*Static
0.1, 1., 1.e-6, 0.1
*Boundary
BASE, 1, 3, 0.
TOP, 3, 3, -0.01
*Output, field
*Node Output
U, RF
*Element Output
S, E
*End Step
"""

_SIGNS = ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
          (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))


def validate_inp(text: str) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    required = ("*Element, type=C3D8, elset=EALL", "*Nset, nset=BASE",
                "*Nset, nset=TOP", "*Material, name=STEEL", "*Elastic",
                "*Solid Section, elset=EALL, material=STEEL",
                "*Step, name=STATIC, nlgeom=NO", "*Static", "*Boundary",
                "BASE, 1, 3, 0.", "TOP, 3, 3, -0.01", "*Output, field",
                "*Node Output", "U, RF", "*Element Output", "S, E", "*End Step")
    missing = [item for item in required if item not in lines]
    if missing:
        raise ValueError(f"missing required INP content: {missing}")
    node_start = lines.index("*Node") + 1
    element_start = lines.index("*Element, type=C3D8, elset=EALL")
    nodes = {}
    for line in lines[node_start:element_start]:
        values = [part.strip() for part in line.split(",")]
        if len(values) != 4:
            raise ValueError("invalid node record")
        index = int(values[0])
        if index in nodes:
            raise ValueError("duplicate node")
        nodes[index] = tuple(float(value) for value in values[1:])
    if set(nodes) != set(range(1, 9)):
        raise ValueError("expected exactly eight nodes")
    element = [int(part.strip()) for part in lines[element_start + 1].split(",")]
    if element != [1, *range(1, 9)]:
        raise ValueError("expected one C3D8 with node order 1..8")
    if lines[element_start + 2] != "*Nset, nset=BASE":
        raise ValueError("expected exactly one element")
    if lines[lines.index("*Nset, nset=BASE") + 1] != "1, 2, 3, 4":
        raise ValueError("base node set differs from fixed face")
    if lines[lines.index("*Nset, nset=TOP") + 1] != "5, 6, 7, 8":
        raise ValueError("top node set differs from loaded face")
    if lines[lines.index("*Elastic") + 1] != "210000., 0.3":
        raise ValueError("material parameters differ from requested values")
    if lines[lines.index("*Solid Section, elset=EALL, material=STEEL") + 1] != ",":
        raise ValueError("solid section data line missing")
    if lines[lines.index("*Static") + 1] != "0.1, 1., 1.e-6, 0.1":
        raise ValueError("static step controls differ")
    if lines.count("*Step, name=STATIC, nlgeom=NO") != 1 or lines.count("*End Step") != 1:
        raise ValueError("expected exactly one complete static step")
    if lines[-1] != "*End Step":
        raise ValueError("trailing analysis content after step")
    if {nodes[i] for i in range(1, 5)} != {(0., 0., 0.), (1., 0., 0.),
                                           (1., 1., 0.), (0., 1., 0.)}:
        raise ValueError("base face geometry differs from unit cube")
    if {nodes[i] for i in range(5, 9)} != {(0., 0., 1.), (1., 0., 1.),
                                           (1., 1., 1.), (0., 1., 1.)}:
        raise ValueError("top face geometry differs from unit cube")

    # Isoparametric C3D8 Jacobian at the element center; positive orientation is required.
    jacobian = [[sum(nodes[i + 1][axis] * _SIGNS[i][direction] / 8
                     for i in range(8)) for direction in range(3)] for axis in range(3)]
    a, b, c = jacobian
    determinant = (a[0] * (b[1] * c[2] - b[2] * c[1])
                   - a[1] * (b[0] * c[2] - b[2] * c[0])
                   + a[2] * (b[0] * c[1] - b[1] * c[0]))
    if not math.isclose(determinant, 0.125, rel_tol=0, abs_tol=1e-12):
        raise ValueError(f"unexpected C3D8 center Jacobian: {determinant}")
    return {"nodes": 8, "elements": 1, "jacobian_at_center": determinant,
            "bottom_fixed": True, "top_displacement_mm": -0.01,
            "youngs_modulus_mpa": 210000, "poisson_ratio": 0.3,
            "requested_outputs": ["U", "RF", "S", "E"]}


def write_if_absent(path: Path) -> str:
    validate_inp(INP)
    data = INP.encode("ascii")
    if path.exists():
        if path.is_file() and path.read_bytes() == data:
            return "REUSED_IDENTICAL"
        raise FileExistsError(f"refusing to overwrite existing file: {path}")
    if path.parent.exists() and any(path.parent.iterdir()):
        raise FileExistsError(f"target directory is not empty: {path.parent}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as output:
        output.write(data)
    return "CREATED"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if args.check_only:
        print(validate_inp(args.path.read_text(encoding="ascii")))
    else:
        print(write_if_absent(args.path))
        print(validate_inp(args.path.read_text(encoding="ascii")))
