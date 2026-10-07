# Owner-approved contour adoption — Nambli 1.001

On 2026-10-08, Yurii Tor reviewed the linked final proof and instructed
continuation. It contains eight changed glyph/face pairs and 48 unchanged
side-caron controls. The owner also reports submitting the GF Designer Profile
form. The public `catalog/designers/yuriitor` path still returned HTTP 404;
form submission is recorded separately from Google catalog publication.

## Adopted sources and files

The UFO tree is byte-identical to reviewed candidate
`546f092e6045c9f190fc4b747ceb2f1188c4b65e`: all 12,060 source files were independently
compared. Against the prior QA head, only eight GLIF outlines and twelve
version records change. The GLIF advance widths, Unicode, anchors and other
non-outline metadata remain identical; feature files and kerning are unchanged.

Changed pairs: Bold U+A7C8 / U+02A6; BoldItalic U+A7C8; LightItalic U+00B6;
Medium U+1D7D; MediumItalic, SemiBold and SemiBoldItalic U+02A3.

Candidate TTF/WOFF2 files are committed under `fonts/candidates/1.001/`.
All 24 files are byte-identical to the exact candidate used by the owner's
review page. Existing `fonts/ttf`, `fonts/webfonts` and supplementary
`fonts/otf` remain released version 1.000. No 1.001 OTF is claimed.
The released tag/assets and website are outside this update.

## Build and preservation validation

- Clean and repeated production Fontmake builds: PASS; all 24 TTF/WOFF2 SHA-256
  hashes match between runs.
- Source-to-build validation: 11,976 glyph instances, twelve faces, PASS.
- Specialized reference audit: exactly eight changed contours; 105,696 shaping
  comparisons PASS, no metric/layout/kerning changes, exact cmap and glyph order.
- Each face retains 970 encoded characters and 998 glyphs.
- WOFF2 decompression preserves tested tables and outlines.
- Nine strict QA-runner regression tests: PASS.
- `git diff --check`: PASS before committing.

See [build-validation.json](build-validation.json),
[candidate-audit.json.gz](candidate-audit.json.gz),
[adopted-sources.json](adopted-sources.json) and
[adoption-manifest.json](adoption-manifest.json).
The automated validator explicitly does not assess visual approval; that
approval is recorded above instead of changing historical native reports.

## Final package validation

The source/binary commit is `eafe6884f5c75aaa395479cc0176b54b7ed9b6d5`.
Google import commit `44b736f59ad3f24845e39a025eb380149e1a9fff` pins it in
`METADATA.pb`, with all twelve font mappings pointing into
`fonts/candidates/1.001/ttf`. All 18 metadata source mappings are byte-identical
to the files at that real committed source revision. All 19 committed family
files match the exact Git-index bytes used in both full-profile runs.

| Full network profile, 18 explicit inputs | PASS | WARN | FAIL | ERROR / FATAL | SKIP | INFO | Exit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Official stock Fontspector 1.8.0 | 1161 | 145 | 16 | 0 / 0 | 688 | 81 | 1 |
| Same CLI with locally patched NAM data | 1162 | 145 | 0 | 0 / 0 | 688 | 81 | 0 |

Both runs execute `googlefonts/tofu`, use no exclusions, preserve all inputs,
and record executable SHA-256, full commands, exact inputs and native status.
The stock run remains a FAIL. The patched run is a local candidate PASS;
upstream acceptance, an official corrected dependency and serving rollout are
not established by it. Four overlap and two jaggy-join WARN disappear compared
with the previous 151-WARN full package. The two remaining jaggy-join warnings
are retained in the owner's reviewed geometry rather than declared fixed.

See [package-manifest.json](package-manifest.json), [stock summary](reports/stock/summary.redacted.json),
[patched summary](reports/patched/summary.redacted.json) and [evidence-manifest.json](evidence-manifest.json).
Native local reports/logs remain untouched. Public copies are explicitly
path-redacted and compressed where appropriate, with original/public hashes;
JSON redaction reserializes the copies without changing check results.

The official serving-data blocker remains tracked in
[NAM #31](https://github.com/googlefonts/nam-files/pull/31) and
[Fontspector #946](https://github.com/fonttools/fontspector/issues/946).
This adoption changes contours, not the missing subset arrays or Google rollout.

## Reproduction

Install pinned `requirements.txt` in an isolated Python environment. On Windows,
use UTF-8 mode (`python -X utf8`). Run from this source checkout with fresh
output directories:

```sh
python sources/build_fontmake.py --output build-adoption --verify-reproducible
python sources/validate_outline_candidate.py --baseline fonts/ttf --candidate build-adoption --output adoption-audit.json
python -m unittest discover -s sources -p test_run_qa.py -v
python sources/run_qa.py --scope package --family GOOGLE_CHECKOUT/ofl/nambli --executable STOCK_EXECUTABLE --output qa-adoption-stock --mode network --tool-kind stock
python sources/run_qa.py --scope package --family GOOGLE_CHECKOUT/ofl/nambli --executable PATCHED_EXECUTABLE --output qa-adoption-patched --mode network --tool-kind patched-candidate
```

Use the exact source and Google import commits above. Resolve tool placeholders
using the pinned setup in [REPRODUCE.md](../../2026-10-07/REPRODUCE.md).
Stock is expected to exit 1 with sixteen subset-data failures; the separately
identified local patched executable exits 0. Neither result is relabeled.

The historical dated reports and proof remain unchanged. No new browser or OTF
test is implied by these source/build checks. Since the candidate bytes match
the approved proof exactly, no new design choice is introduced by adoption.

