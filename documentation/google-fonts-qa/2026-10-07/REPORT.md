# Nambli Google Fonts QA — 2026-10-07–08

The approved 1.000 font binaries are complete; their declared serving subsets
omit required combining marks. A locally built Fontspector with the proposed
NAM data passes the full package. **Stock Fontspector still reports 16 FAIL.**
The data patch alone does not fix every browser result: a separate, implemented
serving proposal keeps Latin words and marks together, preserves all 970 encoded
characters, and is tested against the full fonts. Neither proposal has been
accepted or deployed upstream. Google PR #11086 remains a draft.

## Changes and status

| Item | Status |
| --- | --- |
| Strict package QA runner, scope/exit/hash regression tests and CI | FIXED_IN_PROJECT |
| Article, three actual Nambli JPEG specimens, image license and source mappings | FIXED_IN_PROJECT |
| Editable NAM inputs, official regeneration, four Rust regression tests, Cargo path override | PATCH_VERIFIED_LOCALLY |
| Coherent, full-repertoire WOFF2/CSS serving model | PATCH_VERIFIED_LOCALLY; REQUIRES_UPSTREAM_ACCEPTANCE/ROLLOUT |
| Separate 1.001 outline candidate | PATCH_VERIFIED_LOCALLY; NEEDS_OWNER_INPUT |
| Designer profile structure and verified-fact biography draft | NEEDS_OWNER_INPUT: chosen portrait and approved bio/link |
| Firefox and real Safari/iOS | NOT_TESTED |

No styles, glyphs, languages or sample texts were removed. No primary_language,
fake metadata subset, check exclusion, severity downgrade, manual raw-report
edit, global metric change or borrowed vendor ID was used. The published tag,
release assets and site were not changed. The Google head contains only the
article/images and verified metadata source reference; no experimental NAM,
Cargo patch or 1.001 font is included.

## Exact inputs and tools

* Approved source/release: `7492b115b65043f99475c65374ff7cad39543cfa`, `v1.0.0`,
  font version 1.000. All 12 faces have 970 encoded characters / 998 glyphs.
* QA branch starts from develop `6416b5589f32fcad54a6133e3092918ed83d5312`.
  Staged Google source.commit is
  `8083e024eb3e74493b255b83f0d7b0f5e677ab23`, an actual pushed source/artwork commit.
  Its production UFOs and TTFs match the approved fonts exactly.
* Historical Fontspector and latest stable CLI: **1.8.0**,
  [`3ec1edc05c80631440d8d0e94f35a0c6570744da`](https://github.com/fonttools/fontspector/tree/3ec1edc05c80631440d8d0e94f35a0c6570744da).
  The CLI release channel was checked separately from profile crate releases
  and rechecked on 2026-10-08; it remains 1.8.0.
  Newly downloaded official Windows executable SHA-256:
  `443b250a03f29ed5b48d59aa3905f766a2848eea52a886c8a2e33f6e87bb5df5`.
  It is byte-identical to the historical executable.
* Stock Cargo.lock uses google-fonts-subsets **0.202602.1**, crate SHA-256
  `597758334cd2e74730da9e4c6d970f9d6b32bdb6823b1f9c2272720615f12252`,
  and google-fonts-languages **0.7.11**, crate SHA-256
  `a8066b43e3021c9ba25242b7e2fa57a9f1d1f77fa8ae43936f6946512a3f2376`.
* Patched data checkout:
  [`nam-files 2a68014b16056e965c18fd47de1f3fde9a5b0095`](https://github.com/googlefonts/nam-files/tree/2a68014b16056e965c18fd47de1f3fde9a5b0095).
  Its eleven pre-existing Latin-ext additions versus the published crate are
  **all absent from Nambli's cmap**, so they cannot explain the removed failures.
  The other three declared sets are identical before our patch.
* Regeneration uses the official `scripts/preprocess_namfile.py`, youseedee 0.7.0
  and frozen Unicode **18.0.0** ZIP SHA-256
  `7b3e555514060b92290d154f53655c5eb0fa62b16eb04c03434ff72d1a66a0d8`.
  Regenerating all four unchanged inputs reproduces the tracked outputs;
  see nam-regeneration-baseline-four.json. Unicode 17 was
  rejected after producing unrelated removals; it was not used for the patch.
* Rust/cargo 1.98.0 on Windows MSVC. Patched executable SHA-256:
  `30f8e4e1d93b6605dc6babb06d5cd26599ed1144ce469449ef7d479cc1e10535`.
  The Cargo metadata record proves subsets resolved to the local path; language
  data remains the original registry dependency. `tofu.rs` and check code are
  unchanged. Current upstream `tofu.rs` was compared and has the same behavior.
* Python 3.14; production dependencies: Fontmake 3.12.1, ufo2ft 3.9.1,
  FontTools 4.66.1, uharfbuzz 0.56.3, Brotli 1.2.0. Python's NFC/NFD tables are
  Unicode 16.0.0; this is distinct from the pinned NAM regeneration database.

## Full, unsuppressed package results

Every row runs the complete `googlefonts` profile, network enabled, no exclusions.
Counts are native **subresults**, not check totals. Raw output, native exit status,
before/final input hashes and executable hashes are recorded per run.

| Run | Scope / explicit inputs | PASS | FAIL | ERROR | FATAL | WARN | SKIP | INFO | Native exit |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stock baseline 1.8.0 | Original package: 12 TTF + metadata + OFL + article (15) | 1154 | 16 | 0 | 0 | 152 | 688 | 81 | 1 |
| Stock latest 1.8.0 | Same immutable 15 inputs | 1154 | 16 | 0 | 0 | 152 | 688 | 81 | 1 |
| Patched final candidate 1.8.0 | Same immutable 15 inputs | 1155 | 0 | 0 | 0 | 152 | 688 | 81 | 0 |
| Stock final Git-index package | 19 family files; 18 explicit inputs, including 12 unchanged TTF, metadata, OFL, article and 3 JPEG | 1155 | 16 | 0 | 0 | 151 | 688 | 81 | 1 |
| Patched final Git-index package | Exactly the same 19 files / 18 explicit inputs | 1156 | 0 | 0 | 0 | 151 | 688 | 81 | 0 |

`googlefonts/tofu` executes without SKIP in every package row. The sixteen
failure messages become **one aggregate PASS**, not sixteen invented PASS
messages. Article images account for the one warning removed in the final run.
The nineteenth file is article/image-license.txt; it is present, source-mapped
and hashed, although it is not an explicit Fontspector check input. All final
source.commit/image/license mappings were present before those final runs.
Exact staged Git bytes were exported and tested before committing. All twelve
font bytes and the OFL Git blob are unchanged. The immutable Windows baseline
has CRLF text, while Git stores LF: baseline OFL SHA-256 is
`8f54c3c154295651b48bd01c23fd4db0bd8069be3141ff06ca766a0a50ee8c1b`,
the unchanged Git OFL blob is
`64839c62885a8cb1fb22c54b4aa373e8582613c087ed36d0b412faadb8c2a7ea`.
This newline distinction changes no license content or published release asset.
Earlier 18-file worktree runs are retained as historical evidence, not silently
relabelled as the final Git-index package. See final-index-package.json.

Binary QA is a different scope: 12 explicit TTFs with OFL present and hashed, no metadata or
article. Stock approved 1.000: 1127 PASS / 134 WARN / 704 SKIP / 80 INFO,
native exit 0. The separate 1.001 candidate: 1133 PASS / 128 WARN / 704 SKIP /
80 INFO, native exit 0. Tofu does not execute there; neither is a package PASS.
An isolated `nambli` import directory is required for binary QA. A trial using
the nested baseline import directory triggered a license-discovery failure;
it was an input-layout error, and the corrected isolated binary run is retained.
An initial sandbox network run returned 49 network ERROR; its native report is
retained locally and is not characterized as a font defect. The unrestricted
network reruns above have zero ERROR/FATAL. No report was edited to hide it.

See [report-manifests.json](report-manifests.json) and `reports/`. Public raw
copies are gzip-compressed and **explicitly path-redacted**; original raw JSON
and logs remain untouched locally. Their original SHA-256 values are retained.
See [EVIDENCE-NOTICE.txt](EVIDENCE-NOTICE.txt).

## Cause of all sixteen original subresults

The exact-tag [tofu implementation](https://github.com/fonttools/fontspector/blob/3ec1edc05c80631440d8d0e94f35a0c6570744da/profile-googlefonts/src/checks/googlefonts/tofu.rs)
selects the first metadata font (Nambli-Light), determines language support,
normalizes samples to NFC, removes LF, and compares sample codepoints with the
union of declared subset arrays. A full-font comparison succeeds before the
subset comparison fails. `menu` is a dynamic special case without a fixed NAM
array; it cannot supply these missing marks. Updating Python gfsubsets would
not update the Rust data embedded in the stock executable.

| Language / sample | Missing codepoints in stock | Minimal real clusters | Final local result |
| --- | --- | --- | --- |
| Aghem agq_Latn / specimen_16 | 030C, 1DC7 | ɨ̌, o᷇ | No missing marks; coherent all-12 PASS |
| Aleut ale_Latn / specimen_16 | 0302 | x̂ | No missing marks; coherent all-12 PASS |
| Amarakaeri amr_Latn / specimen_16 | 0331 | e̱, o̱ | No missing marks; coherent all-12 PASS |
| Chickasaw cic_Latn / poster_md | 0331 | a̱, ó̱ | No missing marks; coherent all-12 PASS |
| Chinantec Chiltepec csa_Latn / specimen_16 | 0331 | a̱, o̱ | No missing marks; coherent all-12 PASS |
| Dar Daju Daju djc_Latn / masthead_partial | 0330 | N̰ | No missing marks; coherent all-12 PASS |
| Fur fvr_Latn / masthead_partial | 0331 | A̱, a̱ | No missing marks; coherent all-12 PASS |
| Jarai jra_Latn / specimen_16 | 0306 | ơ̆ | No missing marks; coherent all-12 PASS |
| Lingala ln_Latn / specimen_16 | 0302, 030C | ɔ̂, ɔ̌ | No missing marks; coherent all-12 PASS |
| Mendankwe Nkwen mfd_Latn / specimen_16 | 030C | ə̌ | No missing marks; coherent all-12 PASS |
| Nuer nus_Latn / masthead_full | 0331 | Ɛ̱̈, ɛ̱̈ | No missing marks; coherent all-12 PASS |
| Otomi Mezquital ote_Latn / specimen_16 | 0331 | u̱ | No missing marks; coherent all-12 PASS |
| Secoya sey_Latn / specimen_16 | 0331 | o̱ | No missing marks; coherent all-12 PASS |
| Siona snn_Latn / poster_lg | 0331 | i̱ | No missing marks; coherent all-12 PASS |
| Ticuna tca_Latn / specimen_16 | 0331 | a̱ | No missing marks; coherent all-12 PASS |
| Uduk udu_Latn / specimen_16 | 0331 | p̱ | No missing marks; coherent all-12 PASS |

[investigation.json](investigation.json) preserves the exact texts, source-data
hashes and all **72** UFO/TTF mark records. Each of 0302 / 0306 / 030C / 0330 /
0331 / 1DC7 exists in every UFO and TTF, maps correctly, has nonempty contours,
zero advance, GDEF mark class 3 and relevant GSUB / mark / mkmk tables. Each is
absent from all four declared stock arrays and the unpatched current NAM arrays.
Actual placement and stacking are verified by shaping, not inferred from table
presence. The control corpus includes bases in both Latin and Latin-ext.

## Implemented data and serving patches

The [NAM patch](patches/nam-subset-marks.patch.gz) changes editable inputs and their
official regenerated outputs, without unrelated removals:

* Latin and Latin-ext: the six failure marks, cedilla 0327 for real `m̧ / ə̧`
  clusters, and 0307 / 030A / 030B / 0326 / 0328 for modern Swedish, Lithuanian,
  Turkish, Hungarian, Romanian and Polish NFD controls.
* Vietnamese: structural 0302 / 0306 / 031B and six intermediate canonical
  vowels ÂÊÔâêô used when shaping stacked vowel/tone marks.
* Cyrillic: 0300 / 0306 / 0308 for modern Ѝ / Й / Ї / Ё NFD forms; 0301 already exists.

Four Rust tests pass. The [Cargo patch](patches/fontspector-local-nam.patch)
uses a workspace-root `[patch.crates-io]`; the lockfile only drops the registry
source/checksum for the locally resolved subsets package. Actual dependency
resolution is recorded in [cargo-resolution.json](cargo-resolution.json).
No language or validator source was changed. The approach follows
[Cargo's dependency override rules](https://doc.rust-lang.org/cargo/reference/overriding-dependencies.html).

The NAM-only approach is **not sufficient for production**. Literal patched
splits still show 132 differing Chromium renders / 180 WebKit renders out of
576 each. The Latin-ext-only experiment is worse (444 / 468), including real
fallback. Splitting Latin words across physical fonts loses kerning; overlapping
ranges and canonical compositions can choose a different subfont. Twenty-four
native minimal-cluster comparisons still differ with literal patched splits.
[NAM #6](https://github.com/googlefonts/nam-files/issues/6) and
[NAM #23](https://github.com/googlefonts/nam-files/issues/23) informed the tests;
their historical comments were not treated as current proof.

The implemented second candidate:

1. Coalesces the declared Latin / Latin-ext / Vietnamese repertoires into one
   physical Latin/common WOFF2 for each style, retaining layout closure and
   canonical intermediate cmap compositions.
2. Keeps Cyrillic in a separate coherent WOFF2, including encoded historical
   forms. Every other encoded character, including symbols and extra marks,
   remains in Latin/common; the union is asserted equal to the full cmap.
3. Uses actual `@font-face` and `unicode-range` declarations, keeping metadata
   labels unchanged. This is a **backend/CSS-serving proposal**, not a hidden
   assertion that Google's current private pipeline works this way.

It retains all **970 × 12 = 11,640** encoded character mappings/shapes, and passes
576 whole-text and 1,284 minimal-cluster comparisons against the original TTFs.
Glyph names, clusters, offsets and advances are compared; renumbered numeric
glyph IDs are not compared across subsets. The trade-off is a larger first
Latin download; subset-shaping-manifest.json.gz records actual byte sizes for every WOFF2.
Google acceptance, data/crate publication, serving routing and API rollout are
still external actions. The patch is not presented as a deployed service fix.

## Browser evidence and build validation

The fixture contains 180 actual WOFF2 files across the full font, stock sets,
Latin-ext-only experiment, literal patched sets and coherent candidate. The
corpus has 48 rows: all 16 exact failing samples in NFC/NFD and eight controls
in NFC/NFD (including stacked Nuer, Ukrainian, Vietnamese and modern Latin).
Original text and LF are retained in the corpus; line shaping removes LF
explicitly, matching tofu, rather than substituting sample content.

| Engine | Version | 12-style text checks | Coherent differing images | Status |
| --- | --- | ---: | ---: | --- |
| Chromium | 153.0.8010.12, Playwright 1.62.1 | 576 | 0 | PASS |
| Playwright WebKit for Windows | 26.5, Playwright 1.62.1 | 576 | 0 | PASS |
| Firefox | executable absent | 0 | — | NOT_TESTED |
| Real Safari/iOS | unavailable | 0 | — | NOT_TESTED |

Each tested engine receives 180 successful WOFF2 responses, waits for actual
loads and `fonts.ready`, and compares canvas pixels and advances. Chromium's
selected Regular/Italic DOM controls also have platform-font diagnostics:
full/coherent controls use Nambli custom fonts, while stock controls demonstrate
system fallback. These diagnostics are a selected 24-node sample, not an
exhaustive fallback audit of every possible string. Screenshots and complete
per-text outcomes are in [browser/](browser/). Zero differences are evidence
for this corpus/model/size, not every Unicode text, device or Google API.
Playwright WebKit is explicitly **not** a real Safari/iOS test.

The approved production sources were clean-built twice through
`sources/build_fontmake.py`: 11,976 exact glyph comparisons and 105,696 shaping
comparisons pass. All 24 TTF/WOFF2 SHA-256 values repeat, and rebuilt TTFs are
byte-identical to the release. See [approved-clean-build.json](approved-clean-build.json).
The separate candidate is also clean-built twice, matches its editable UFOs,
retains cmap, metrics, kern and OpenType tables, and passes 105,696 shaping
comparisons against 1.000. Eight glyph/face contour pairs and version-dependent
name strings are the only allowed changes. WOFF2 decompression matches the
candidate's actual tables. OTFs are supplementary; no independent OTF build is
claimed, and 1.001 OTFs were not manufactured or mixed with this candidate.
Its source is on `codex/fix/google-fonts-outline-candidate`, commit
[`a44293f7d8c75278df742b6785e927dfbd15b584`](https://github.com/Tor-Production/nambli-font/commit/a44293f7d8c75278df742b6785e927dfbd15b584).
No second project PR is opened; it is a separately versioned review candidate.

## Remaining warnings and owner/external work

Every historical package WARN is dispositioned in
[../../WARNING-DISPOSITIONS.txt](../../WARNING-DISPOSITIONS.txt).
The approved final package retains 151 WARN. None is suppressed. The separate
1.001 candidate addresses all four retraced-segment warnings and two of four
jaggy-join warnings; its binary total is 128 rather than 134. The remaining
sharp ¶ join in LightItalic and bar/counter join in Medium U+1D7D need a visual
decision before more significant smoothing. The candidate review shows all
eight changed pairs and 48 unchanged side-caron controls:
[outline-review/Nambli-Outline-Candidate-Review.html](outline-review/Nambli-Outline-Candidate-Review.html).

The remaining declared-subset gap is 35 encoded characters versus 48 in stock;
all are listed in [repertoire-and-metrics.json](repertoire-and-metrics.json).
The local coherent proposal preserves them. Choosing legitimate Google range
assignments/serving policy remains upstream work, not deletion of those glyphs.
Approved line metrics (1200 / -400 / 0, 1.6 UPM) contain measured ink extents
-326…1182 across all styles; shrinking them risks clipping. Proportional math
spacing, unregistered NAMB vendor ID, legacy family naming and the empty .null
are retained transparently. No vendor registration or new rupee design was
performed on the owner's behalf.

Three 1600×900, 72-dpi article JPEGs are rendered from the checked Nambli TTFs
and each is under 800 KiB. Their CC BY-SA 4.0 license does not replace the OFL
license of the older specimen. Both the
[article guide](https://googlefonts.github.io/gf-guide/article.html) and the
checker size limits are satisfied. The upstream designer catalog did not have
`yuriitor` at the time of inspection. A factual profile draft is in
`documentation/designer-profile-draft`; its portrait is intentionally missing.
No profile form, new external issue or external PR has been submitted.

Pending: upstream review/acceptance of NAM and serving changes, published data
consumption by the validator/backend, Google onboarding/rollout, owner portrait
and biography/link approval, and owner review of the separate contour candidate.
Contributor rights/AI/maintenance confirmations are already complete and are
not requested again. PR #11086 must remain Draft until the owner decides otherwise.

## Reproduction and public change boundary

Use [REPRODUCE.md](REPRODUCE.md) for exact pins, patch application, frozen official
regeneration, Cargo metadata/build/tests, strict package runs, browser generation
and the separate candidate. Draft external English texts are in `upstream-drafts/`;
they are ready to edit/submit only when separately authorized.

No historical raw report was overwritten. Original baseline fonts/OFL/metadata/
article, all release assets and `v1.0.0` are checked against the initial snapshot.
Experimental binaries, dependency caches, private issue snapshots, personal paths
and full third-party checkouts are excluded from the project change.
