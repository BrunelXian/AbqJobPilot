"""Fixed Abaqus Python script for the single proposed T3D2 HIL. Read-only ODB access."""

import json
import math
import sys


def tip_displacement(odb):
    from abaqusConstants import NODAL

    step = odb.steps["LOAD"]
    frame = step.frames[-1]
    if frame.incrementNumber <= 0 or not math.isclose(frame.frameValue, 1.0, abs_tol=1e-9, rel_tol=0.0):
        raise ValueError("ODB_FINAL_FRAME_MISSING")
    field = frame.fieldOutputs["U"]
    components = tuple(field.componentLabels)
    if components.count("U2") != 1:
        raise ValueError("ODB_COMPONENT_MISSING")

    # A flat deck can expose its node set on the root assembly or one instance.
    root = odb.rootAssembly
    regions = [root.nodeSets["TIP"]] if "TIP" in root.nodeSets else [
        instance.nodeSets["TIP"] for instance in root.instances.values() if "TIP" in instance.nodeSets]
    if len(regions) != 1:
        raise ValueError("ODB_REGION_AMBIGUOUS")
    values = field.getSubset(region=regions[0], position=NODAL).values
    if len(values) != 1 or values[0].nodeLabel != 2:
        raise ValueError("ODB_NODE_MISMATCH")
    value = values[0]
    from abaqusConstants import DOUBLE_PRECISION
    data = value.dataDouble if value.precision == DOUBLE_PRECISION else value.data
    result = data[components.index("U2")]
    if not math.isfinite(result):
        raise ValueError("ODB_NONFINITE")
    return {"node": 2, "increment": int(frame.incrementNumber), "step_time": format(frame.frameValue, ".17g"),
            "value_mm": format(result, ".17g")}


def main():
    from odbAccess import openOdb

    if len(sys.argv) != 3:
        raise ValueError("ODB_ARGS_INVALID")
    source, output = sys.argv[1:]
    odb = openOdb(path=source, readOnly=True)
    try:
        try:
            data = {"measurement": tip_displacement(odb)}
        except KeyError:
            data = {"error": "ODB_FIELD_MISSING"}
        except ValueError as exc:
            data = {"error": str(exc)}
    finally:
        odb.close()
    with open(output, "x", encoding="utf-8") as stream:
        json.dump(data, stream, sort_keys=True, allow_nan=False)


if __name__ == "__main__":
    main()
