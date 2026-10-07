# Separate contour QA candidate — font version 1.001

This branch is for visual review. It does not replace the approved v1.0.0
fonts, website or Google Fonts submission. `fonts/ttf` and supplementary OTFs
remain the approved 1.000 reference files; the new 1.001 TTF/WOFF2 must be built
into a separate output directory from the edited production UFOs.

Eight glyph/face pairs are changed: Bold U+A7C8 / U+02A6, BoldItalic U+A7C8,
LightItalic U+00B6, Medium U+1D7D, MediumItalic U+02A3, SemiBold U+02A3 and
SemiBoldItalic U+02A3. Only these contours and the twelve UFO version records
are edited. Selected curve backtracking and rounded intersections are repaired;
two precisely guarded one-unit excursions are removed. TrueType winding is
retained, and point sequences are canonicalized through the compilation pen.

The complete unsuppressed **binary-only** Fontspector 1.8.0 network profile has
1133 PASS / 128 WARN / 704 SKIP / 80 INFO / 0 FAIL/ERROR/FATAL, native exit 0.
Four overlap warnings and two jaggy-join warnings are removed. Two jaggy-join
warnings remain (LightItalic ¶ and Medium U+1D7D); more visible smoothing needs
a design decision. This is not a Full Google Fonts package PASS or owner approval.

All twelve faces retain 970 encoded characters / 998 glyphs, cmap, metrics,
OpenType layout, kern and language shaping. Clean/repeat TTF/WOFF2 builds pass
the source audit and have identical SHA-256; 105,696 reference shaping tests
pass. No reproducible candidate OTF build is claimed.

Use the pinned production Python requirements, plus skia-pathops 0.9.2, in a
task-local environment. The preparation script uses exact geometry guards and
refuses to edit a branch other than `codex/fix/google-fonts-outline-candidate`.
To reproduce the source edits from an approved clean source checkout:

```sh
python sources/prepare_outline_qa_candidate.py --worktree . --baseline-ufos APPROVED_CHECKOUT/sources/ufos --reference-fonts APPROVED_CHECKOUT/fonts/ttf --report source-changes.json
python sources/build_fontmake.py --output build-candidate --verify-reproducible
python sources/validate_outline_candidate.py --baseline APPROVED_CHECKOUT/fonts/ttf --candidate build-candidate --output candidate-audit.json
python sources/make_outline_qa_review.py --baseline APPROVED_CHECKOUT/fonts/ttf --candidate build-candidate --output candidate-review
```

The approved checkout's UFOs must be a separate directory. The script reads
approved 1.000 TTF geometry and preserves original GLIF non-outline metadata;
those reference binaries are not needed by the production Fontmake compiler.
The specialized audit allows exactly the eight listed contour changes and
1.001 name/version strings; all other outlines and shaping must match 1.000.
Open `candidate-review/Nambli-Outline-Candidate-Review.html` for genuine
before/after contours and all 48 unchanged side-caron controls.

The primary QA branch `codex/fix/google-fonts-qa` contains the dated full
package reports, redacted native evidence, serving experiment and warning
dispositions. This candidate is linked for review from that single draft PR;
it is not separately proposed for merge, release or deployment.
