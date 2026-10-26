# Deterministic, non-authenticating regression inputs

`standard_axial_cp936.txt` is authored text, **not an Abaqus run**. The one localized month glyph exercises strict CP936 handling. The fixed R010 heading is required by the existing narrow parser, not a provenance claim. Step/increment/entity/component/final footer are explicit. Missing node-2 reaction remains missing; it must not be inferred as zero.

`diagnostic_v2.json` is an invented historical-format public envelope: fixed identifiers, time 1000, no paths, credentials, process identities or real execution facts. Its deliberately absent managed fields test backwards compatibility; its one FAIL validation tests both allowed validation-source values. Extra-field injection must still fail.

`generate.py` reproduces these files from literal invented content and the public projection schema. Tests read the checked-in files; they do not regenerate against a changed schema or read excluded historical material. Update requires deliberate fixture review. Neither file is execution evidence or authorization.

Original Run007 JSON and Run011 DAT remain untouched in local historical evidence. Synthetic coverage preserves the maintained tests' assertions, not every formatting variation in that real DAT. Historical acceptance remains separately documented.
