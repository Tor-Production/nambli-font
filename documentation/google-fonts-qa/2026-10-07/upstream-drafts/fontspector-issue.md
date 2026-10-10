# Draft only — not submitted

Suggested title: Required NAM marks and split-font cluster regressions in tofu coverage

The official Fontspector 1.8.0 Windows CLI reproduces sixteen missing-subsetted
messages for Nambli's full Google Fonts import. Its locked subset crate is
google-fonts-subsets 0.202602.1; language data is google-fonts-languages 0.7.11.
The required six marks exist and shape correctly in every full font. The
declared NAM union excludes them. Current tofu.rs has the same union-based
behavior as the exact release tag.

We prepared a NAM data patch, not a severity/exclusion workaround. A workspace
root [patch.crates-io] overrides only the subset dependency; cargo metadata/tree
prove its actual local resolution. Language and validator source stay unchanged.
The same immutable 15-input package changes from native exit 1 with 16 FAIL /
152 WARN to native exit 0 with 0 FAIL/ERROR/FATAL / 152 WARN. Four NAM Rust tests
and all-face shaping tests cover the missing marks and modern NFD controls.

The union test remains useful but does not prove actual split-font rendering.
Literal patched WOFF2 subsets still differ on 132/576 Chromium and 180/576
Playwright WebKit renders, while an implemented full-repertoire coherent
Latin/common + Cyrillic serving proposal has zero differences. These numbers
are local NAM/fontTools/CSS model evidence, not a Google private backend test
or real Safari/iOS test. Full glyph-name/position/advance, requests, selected
platform-font diagnostics and screenshots are retained.

Requested coordination:

1. Review and release the NAM data fix, then consume its actual published crate
   version/checksum through the normal Fontspector dependency process.
2. Consider independent subfont/cluster regression coverage alongside the
   existing union test, without excluding tofu, narrowing languages or downgrading
   missing-subsetted severity.
3. Coordinate with serving maintainers before interpreting a union PASS as a
   production rendering fix.

No permanent local-path dependency should be merged upstream. The included Cargo
patch is only a controlled reproduction experiment; a dependency-update PR needs
the actual released NAM crate pin and cannot truthfully be created before that
release. No validator source defect was shown to justify modifying check logic.

Evidence: Tor-Production/nambli-font, branch codex/fix/google-fonts-qa,
documentation/google-fonts-qa/2026-10-07/REPORT.md and REPRODUCE.md.
Original Google import remains draft at google/fonts#11086. Contributor
confirmations are complete; acceptance and service rollout remain unconfirmed.
