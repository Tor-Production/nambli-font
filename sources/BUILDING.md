# Building Nambli

The editable static masters for the Google Fonts candidate are the twelve UFO3
directories in `sources/ufos`. They include quadratic outlines, Unicode mapping,
metrics, kerning and OpenType feature source. No installed font, network font
service or binary reference font is needed to build them.

From the repository root, install Python dependencies and build:

```sh
python -m pip install -r requirements.txt
python sources/build_fontmake.py
```

The output is twelve TTFs and twelve losslessly compressed WOFF2 files in
`build-fonts/`. The build also validates the UFO outlines, character mapping and
metrics against the compiled fonts. It refuses to overwrite font files; use a
fresh output directory for another run.

For a complete repeat-build and comparison with the committed candidate TTFs:

```sh
python sources/build_fontmake.py --output build-verification --reference-fonts fonts/ttf --verify-reproducible
```

Expect a PASS report at `build-verification/build-validation.json`, identical
SHA-256 values for both builds, and no differences in tested outlines, metrics
or shaping. The second output directory is `build-verification-repeat/`.

The pipeline runs Fontmake with quadratic outlines retained, no autohinting,
and explicit feature source. Legacy `kern` and `STAT` are generated from
editable UFO kerning and library data. There is no transplantation of compiled
layout tables from reference binaries. `--reference-fonts` is only a validation
input. A fixed build timestamp makes repeated builds comparable.

## Google Fonts checks

Use Fontspector 1.8.0 with the `googlefonts` profile. The upstream repository's
`fonts/ttf` layout follows the upstream guide. For the Google Fonts import-layout
check, copy the twelve TTFs and `OFL.txt` to a temporary directory named `nambli`.
Then run, using the executable appropriate for your platform:

```sh
fontspector -p googlefonts --json fontspector.json nambli/*.ttf
```

PowerShell users can pass an array of paths obtained with
`Get-ChildItem nambli -Filter *.ttf`. Network checks need internet access.
`--skip-network` is useful offline but must be reported as skipped coverage.
WARN and SKIP findings require their own interpretation; a zero-FAIL report
does not establish design quality or Google Fonts acceptance.

## Reviewing changes against v0.7.4

Extract the public v0.7.4 archive to a separate directory and locate its TTF
folder. Use that folder as the baseline (replace `BASELINE_TTF_DIRECTORY`):

```sh
python sources/verify_previous_release.py --baseline BASELINE_TTF_DIRECTORY --candidate fonts/ttf --report previous-release-comparison.json
python sources/make_review.py --baseline BASELINE_TTF_DIRECTORY --fonts fonts/ttf --output review-output
```

The comparison permits only the documented design repairs to `@`, `ɬ` and `Ɬ`;
every previous character mapping and metric must remain identical. It compares
exact curve geometry while ignoring redundant zero segments and contour start
rotation. The review page lists every new or changed outline, including
unencoded layout alternatives, with all twelve styles and language examples.

## Historical construction sources

`build_family.py`, `master/`, and the earlier Python construction scripts retain
the development history. They are not the production entry point for this new
candidate and do not recreate all later language and layout additions by
themselves. The UFOs are the complete current editable masters.
Historical construction dependencies are retained in `requirements-design.txt`.

Supplementary CFF/OTF candidates were prepared through the construction
pipeline. The independently rebuilt and repeat-verified production formats in
this change are TTF and WOFF2. OTF conversion from the UFOs remains separate
follow-up work before claiming the same reproducible-build coverage for OTF.
