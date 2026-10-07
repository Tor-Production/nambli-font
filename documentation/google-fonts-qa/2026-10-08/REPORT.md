# Fresh-input audit and upstream submissions — 2026-10-08

The sixteen stock tofu failures do not come from an old font file or a stale
local cache. All nineteen files were downloaded again from the exact public
Google PR head, each Git blob SHA was verified, and every file matches the
previously tested final Git package. The full stock profile still reports
**16 FAIL / 151 WARN / 0 ERROR / 0 FATAL**. No stock PASS is claimed.

With the owner's explicit authorization, the verified data correction and
dependency-consumption request are now public:

- [NAM draft PR #31](https://github.com/googlefonts/nam-files/pull/31),
  branch `Tor-Production:codex/fix/nambli-combining-subsets`, commit
  `feaaf382cb475029368914468eb6708cc4e4cdba`, based on NAM main
  `2a68014b16056e965c18fd47de1f3fde9a5b0095`.
- [Fontspector issue #946](https://github.com/fonttools/fontspector/issues/946)
  tracks consuming accepted/released NAM data and the serving boundary.

Google family PR #11086 and the NAM contribution remain Draft. Publication of
these requests is not acceptance, a released dependency, or deployment. The
published v1.0.0 fonts, release assets and website have not been changed.

## Ruling out an old version

The freshly fetched Google head is `61b4ac3f08aaf42ef24aa1ad4a6a09faf3c54576`.
All twelve fonts say Version 1.000, contain 970 cmap entries / 998 glyphs,
and contain all six required nonempty zero-advance marks. Version 1.000 is the
approved release, not an accidental older 0.x build. Source/artwork metadata
still points to `8083e024eb3e74493b255b83f0d7b0f5e677ab23`.

| Fresh run | Scope | FAIL | ERROR | FATAL | WARN | Native exit |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Official CLI 1.8.0 / freshly downloaded 1.000 | Full googlefonts profile, network enabled, 18 explicit inputs / 19 family files | 16 | 0 | 0 | 151 | 1 |
| Official CLI 1.8.0 / isolated 1.001 contour candidate | Only googlefonts/tofu diagnostic | 16 | 0 | 0 | — | 1 |

The full run has 1155 PASS, 688 SKIP and 81 INFO; tofu executes. Native raw
results, commands, executable hashes and input hashes are in `reports/`.
The 1.001 experiment substitutes only the twelve candidate font files in a
separate local copy and verifies identical cmap. Its unchanged source mapping
does not describe those experimental binaries, so it is explicitly a targeted
diagnostic, not a complete package validation or a replacement submission.
The version/contour change cannot change the missing-subset decision.

Previous full-profile patched-data runs remain valid for these identical
package bytes: 0 FAIL/ERROR/FATAL, 151 WARN, native exit 0, executed tofu.
They are linked in the [original report](../2026-10-07/REPORT.md); they are not
relabeled as new stock runs. Fontspector check code and language samples are
unchanged in that controlled data experiment.

## Exhaustive data and current-tool check

Fresh official upstream queries confirm the latest released CLI is still
`fontspector-v1.8.0` (2026-09-18). The newer
`fontspector-profile-googlefonts-v1.9.1` (2026-09-29) is a profile crate, not a
new released CLI. Current Fontspector main is
`43d6ab52a8355e18714fd035e615a0d5204cd903`; its tofu implementation is byte-identical
to the stock tag and its lockfile still uses subsets 0.202602.1 and languages
0.7.11 with unchanged registry checksums.

An exhaustive scan found U+1DC7 in **none of 187 stock subsets and none of 189
current NAM subsets**. The immutable Aghem sample contains U+1DC7 and NFC
preserves it. The other five marks occur only in eleven unrelated subsets;
Nambli does not meet their coverage thresholds. Its four proper static subset
labels are already declared correctly.

Tofu intersects the actual cmap with the compiled subset arrays. No outline,
version bump, file order, or extra valid cmap entry can add U+1DC7 to an array
that lacks it. The check consumes no per-family Unicode-range override.
Changing `primary_language` cannot narrow its automatic language detection.
The CLI starts with an empty in-process context cache on each invocation, so
an old persistent cmap cache cannot explain the result.

The legitimate path is accepted NAM input/generated-data correction, a
published dataset, and consumption by official Fontspector. The existing
Python selection proposal [NAM #29](https://github.com/googlefonts/nam-files/pull/29)
does not itself add U+1DC7 to any available subset.

## Validation of the submitted NAM patch

The contribution has nine changed files: four editable NAM inputs, four
officially regenerated outputs, and four Rust regression tests in one test
file. No unrelated codepoints are removed. The submitted generated data is
identical to the previously tested local data; only Rust test formatting was
normalized before committing.

`cargo test --locked` passes all four integration tests; unit/doc-test targets
contain no tests. `rustfmt --check tests/nambli_marks.rs` and `git diff --check`
pass. Frozen official UCD 18.0.0 regeneration, Cargo resolution, all-face
shaping and browser evidence are retained in the previous dated report.
The checker/serving limits are stated directly in the public NAM PR and
Fontspector issue. Literal NAM splits still have measured render differences;
the separate coherent WOFF2/CSS model is a locally verified backend proposal.

## WARN are not all defects or all irrelevant

The current approved full package retains **151 WARN across 12 check IDs**.
The original had 152 across 13 IDs; adding real article images removed one.
See [WARN-AUDIT.txt](WARN-AUDIT.txt) and the updated
[dispositions](../../WARNING-DISPOSITIONS.txt).

- 48 side-caron notices say that the component-based check cannot inspect
  decomposed outlines. They require visual review, not automatic redesign.
- 16 non-RIBBI name notices reflect the legacy four-style grouping recommended
  by OpenType for extended families.
- 12 unreachable-subsetting notices and the missing designer profile are real
  remaining onboarding work.
- Eight contour WARN remain in submitted 1.000. The separate 1.001 candidate
  removes six, but needs owner adoption; it does not fix the sixteen tofu FAILs.
- Remaining notices concern layout/spacing choices, approximate joins,
  unregistered vendor ID, optional rupee coverage and an unused empty .null.
  The .null is optional historical retention, not a current requirement.

## Evidence and reproduction

`fresh-submission-manifest.json` records the new download and all nineteen
SHA-256 values. `official-upstream.json`, `all-stock-subsets.json` and
`all-twelve-font-evidence.json` preserve the fresh tool/data and font facts.
`warning-geometry.json` measures the 47 approximate straight joins; none is
mathematically exactly redundant.

Public native reports/logs are explicitly path-redacted copies, compressed for
storage. Their original and public hashes are recorded in each manifest;
the native local originals remain untouched. Redaction also reserializes JSON;
no severities, sample texts, input counts or tool outcomes are changed.

For the current full profile, download `ofl/nambli` from the pinned Google head
and use the strict runner and tool pins in [REPRODUCE.md](../2026-10-07/REPRODUCE.md):

```sh
python sources/run_qa.py --scope package --family /PATH/TO/ofl/nambli --executable /PATH/TO/OFFICIAL/fontspector --output /PATH/TO/NEW/RUN --mode network --tool-kind stock
```

Expect native exit 1 with sixteen missing-subsetted subresults until the
upstream data dependency is corrected. Do not reinterpret a binary-only result,
the local patched executable, or a successful CLA/security workflow as a stock
full-package pass.

Primary references: [CLI release](https://github.com/fonttools/fontspector/releases/tag/fontspector-v1.8.0),
[current tofu source](https://github.com/fonttools/fontspector/blob/43d6ab52a8355e18714fd035e615a0d5204cd903/profile-googlefonts/src/checks/googlefonts/tofu.rs),
[current Cargo lock](https://github.com/fonttools/fontspector/blob/43d6ab52a8355e18714fd035e615a0d5204cd903/Cargo.lock),
[unpatched NAM source](https://github.com/googlefonts/nam-files/tree/2a68014b16056e965c18fd47de1f3fde9a5b0095).
