# Building Nambli

The editable static masters for release 1.0.0 are the twelve UFO3
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

For a complete repeat-build and comparison with the committed release TTFs:

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

## Binary QA

TTF-only QA does not validate the complete Google Fonts import package or its
serving subsets. Use a temporary `nambli` directory containing the twelve TTFs
to satisfy the profile's import-layout expectations:

```sh
python sources/run_qa.py --scope binary --family nambli --executable FONTSPECTOR_EXECUTABLE --output qa-binary
```

Replace `FONTSPECTOR_EXECUTABLE` with a real platform executable. The runner
passes explicit paths, so no shell wildcard expansion is required.

## Full Google Fonts package QA

Check out the actual Google Fonts submission. The family directory must contain
all twelve TTFs, `METADATA.pb`, `OFL.txt`, `article/ARTICLE.en_us.html` and every
referenced article image. Use the unsuppressed complete googlefonts profile:

```sh
python sources/run_qa.py --scope package --family GOOGLE_FONTS_CHECKOUT/ofl/nambli --executable FONTSPECTOR_EXECUTABLE --output qa-package-stock
```

The runner rejects missing inputs or a metadata/font-list mismatch; passes
article images explicitly; preserves raw JSON, stdout/stderr and native exit
status; records before/after SHA-256; and requires `googlefonts/tofu` to execute
without SKIP. It exits nonzero on any FAIL/ERROR/FATAL, unsuccessful native run,
missing report, skipped tofu, or changed input. Reuse of an output directory is
rejected. WARN/SKIP interpretation and Google acceptance remain separate.

Use `--mode offline` for a separately named run when network access is absent.
Network-related skips are then explicit. An offline run is not network QA.

Fontspector 1.8.0 is both the historical baseline and the latest stable CLI
verified on 2026-10-07; the official downloaded executable matches the baseline
SHA-256. The package still fails stock serving checks. Local experiments must
use `--tool-kind patched-candidate` and a separately built executable/output;
they do not establish an upstream fix or service rollout. See
`documentation/google-fonts-qa/2026-10-07/REPORT.md` for the exact versions,
patches and results.

Run the scope/exit-code regression tests:

```sh
python -m unittest discover -s sources -p test_run_qa.py -v
```

These tests also cover absent/skipped tofu, native failure with a superficially
green report, changed inputs, article asset inputs, and output immutability.
On restricted hosts set `NAMBLI_QA_TMPDIR` to a writable scratch directory.

The subset/browser experiments and their limits are reproducible with
`sources/qa_subsets.py` and `sources/run_browser_qa.cjs`; see the dated report.
They use actual WOFF2 assets and compare glyph names/positions rather than
numeric glyph IDs across renumbered subsets. Firefox and Safari/iOS are not
claimed as tested when unavailable.

## Reviewing changes against v0.7.4

Extract the public v0.7.4 archive to a separate directory and locate its TTF
folder. Use that folder as the baseline (replace `BASELINE_TTF_DIRECTORY`):

```sh
python sources/verify_previous_release.py --baseline BASELINE_TTF_DIRECTORY --candidate fonts/ttf --report previous-release-comparison.json
python sources/make_review.py --baseline BASELINE_TTF_DIRECTORY --fonts fonts/ttf --output review-output
```

The comparison permits only the documented design repairs to `@`, `ɬ`, `Ɬ` and `į`;
every previous character mapping and metric must remain identical. It compares
exact curve geometry while ignoring redundant zero segments and contour start
rotation. The review page lists every new or changed outline, including
unencoded layout alternatives, with all twelve styles and language examples.

To compare the latest refinement with a previously saved candidate, pass its
TTF directory as the baseline and add `--refinement --baseline-label previous-candidate
--filename Nambli-Refinement-Review.html`. This includes only changed shapes,
including unencoded alternatives. The committed refinement proof uses the
candidate from commit `671f777` as its baseline.

Check the refined font's actual language substitutions, combining-mark
stacking, loop contours and matching TTF/OTF feature tables with:

```sh
python sources/validate_refinement.py --fonts fonts/ttf --otfs fonts/otf --ufos sources/ufos --report refinement-language-check.json
```

Expect PASS for 216 shaping probes and 60 counter-topology checks across the
twelve faces. This check uses the same pinned Python requirements as the build.

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
