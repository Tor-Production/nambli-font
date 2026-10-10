# Draft only — not submitted

Suggested title: Required combining marks are lost from declared Latin serving subsets

Nambli's Google Fonts import (google/fonts#11086, still draft) reproduces sixteen
`googlefonts/tofu / missing-subsetted` failures using the official Fontspector
1.8.0 CLI and google-fonts-subsets 0.202602.1. Every required mark already exists
in all twelve fonts with zero advance, mark-class GDEF and working mark/mkmk.
The full-font samples succeed; the declared subset union excludes U+0302,
U+0306, U+030C, U+0330, U+0331 and U+1DC7.

Minimal real clusters include Aleut x̂, Aghem o᷇ / ɨ̌, Lingala ɔ̂ / ɔ̌,
Jarai ơ̆ and Nuer Ɛ̱̈. Exact language samples and data hashes are retained;
no language support, sample text or validator severity was changed.

A proposed data patch is prepared against nam-files
`2a68014b16056e965c18fd47de1f3fde9a5b0095`. It adds justified Latin/Latin-ext
marks for both kinds of bases, modern NFD controls, Vietnamese structural marks
and canonical intermediate vowels, and modern Cyrillic NFD marks. Editable
subsets-input and officially regenerated output are included with four Rust
regression tests. Frozen UCD 18.0.0 reproduces the original generated data before
patching, avoiding unrelated Unicode-refresh changes.

This is not a claim that a larger union fixes web serving. Actual WOFF2/CSS
experiments on all twelve styles show remaining font fallback, lost kerning and
canonical-selection differences with literal split fonts. Putting the six
marks only in latin-ext is insufficient. A separate coherent Latin/common and
Cyrillic model retains all 970 encoded characters and matches full fonts for
576 whole-text / 1,284 cluster / 11,640 character checks; Chromium and Playwright
WebKit each match all 576 text renders. That model requires backend/CSS routing
work and is not Google's private pipeline or a real Safari/iOS test.

Would maintainers review the mark/intermediate placements and coordinate the
serving implications described by #6 and #23? NAM data publication alone must
not be treated as rollout of correct cluster serving.

Evidence and patch: Tor-Production/nambli-font, branch codex/fix/google-fonts-qa,
documentation/google-fonts-qa/2026-10-07/REPORT.md and patches/nam-subset-marks.patch.gz
(expand to the standard .patch before applying).
The report includes exact original/patched native output hashes, Cargo resolution,
all sixteen failure cases, browser results and reproduction commands.
