# Draft only — not submitted

Suggested title: Retain required Latin and modern NFD mark clusters in NAM data

The declared Latin subset union currently drops six marks required by supported
language samples. This change adds marks to their real base-bearing script
sets, with generated data kept in sync through the official preprocessor.

Latin and Latin-ext receive 0302/0306/030C/0330/0331/1DC7 plus cedilla 0327 and
modern NFD 0307/030A/030B/0326/0328. Vietnamese receives structural 0302/0306/
031B and ÂÊÔâêô intermediate vowel compositions. Cyrillic receives 0300/0306/
0308 (0301 already exists). The placements are justified by real clusters and
NFC/NFD controls, not by mechanically duplicating marks into every NAM file.
No unrelated codepoints are removed.

Validation:

* Official regeneration using frozen UCD 18.0.0 and youseedee 0.7.0 reproduces
  the original data, then the patched data exactly.
* `cargo test --locked --test nambli_marks`: four regression tests pass.
* Unchanged full Nambli package: stock Fontspector 1.8.0 reports 16 FAIL / 152
  WARN; a local Cargo-resolved NAM build reports 0 FAIL/ERROR/FATAL / 152 WARN,
  native exit 0, tofu executed. The 12 font binaries and samples are unchanged.
* Actual all-face WOFF2 cluster and browser tests are retained, including
  remaining differences with literal patched splits.

This data PR does not independently fix split-font kerning or guarantee that
duplicated unicode-ranges keep every cluster in one subfont. A coordinated
serving decision is required; see the explicit coherent-model proposal and
the existing #6/#23 discussions. No Google backend deployment is claimed.

Patch base: 2a68014b16056e965c18fd47de1f3fde9a5b0095.
Attach the prepared nam-subset-marks.patch and link the dated Nambli QA report.
Update links to the actual submitted upstream branch only after authorization;
this local draft has not been posted.
