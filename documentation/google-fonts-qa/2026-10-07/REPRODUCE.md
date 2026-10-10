# Reproduce the isolated QA and serving candidates

Use a writable task directory and isolated environments. Do not overwrite a
previous run directory. Do not publish these external patches, change a release
tag or deploy the serving model without separate authorization.

## 1. Font sources, tools and immutable input

Check out Nambli `8083e024eb3e74493b255b83f0d7b0f5e677ab23` for the exact
production sources, approved fonts and new article specimens. The QA branch's
later evidence commit adds the scripts/report improvements used below but does
not change those sources/fonts. Use `python -m venv` and install the existing
root `requirements.txt` inside it. See `sources/BUILDING.md` for the actual
build entry point. On Windows use `python -X utf8` for all commands below.

Preserve two family directories named `nambli`: the original 15-file import
package and the final 19-file package from Google PR #11086. Compare their
per-file SHA-256 to the appropriate summary in `reports/`. This package includes
the actual article/assets; the source repo's `fonts/ttf` directory alone is not
package scope. Stock binary-only tests use a separate `nambli` directory with
12 TTFs and OFL.txt, to avoid import-root license-discovery ambiguity. The final
package also carries article/image-license.txt, hashed as a nineteenth family
file; the checker explicitly receives 18 inputs, including the three images.

Download the official **CLI** release `fontspector-v1.8.0` for the host from
https://github.com/fonttools/fontspector/releases/tag/fontspector-v1.8.0.
On the tested Windows host the stock executable SHA-256 is
`443b250a03f29ed5b48d59aa3905f766a2848eea52a886c8a2e33f6e87bb5df5`.
Keep it separately; never rename a patched executable to look stock.

Create sibling shallow clones, then check out the exact pins:

```sh
git clone --depth 1 https://github.com/googlefonts/nam-files.git nam-files
git -C nam-files fetch --depth 1 origin 2a68014b16056e965c18fd47de1f3fde9a5b0095
git -C nam-files switch -c codex/experiment/nambli-marks 2a68014b16056e965c18fd47de1f3fde9a5b0095
git clone --depth 1 --branch fontspector-v1.8.0 https://github.com/fonttools/fontspector.git fontspector
```

Use Python youseedee **0.7.0** in the isolated environment. Download the official
Unicode ZIP https://www.unicode.org/Public/18.0.0/ucd/UCD.zip to `UCD-18.0.0.zip`.
The wrapper verifies its SHA-256 and each extracted file, disables refresh, and
invokes the unchanged official NAM preprocessor:

```sh
python sources/regenerate_nam_pinned.py --nam-repo nam-files --ucd-zip UCD-18.0.0.zip --ucd-dir ucd-18.0.0 --check
python -c "import gzip;from pathlib import Path;p=Path('documentation/google-fonts-qa/2026-10-07/patches/nam-subset-marks.patch.gz');Path('nam-subset-marks.patch').write_bytes(gzip.decompress(p.read_bytes()))"
git -C nam-files apply /ABSOLUTE/PATH/nam-subset-marks.patch
python sources/regenerate_nam_pinned.py --nam-repo nam-files --ucd-zip UCD-18.0.0.zip --ucd-dir ucd-18.0.0
python sources/regenerate_nam_pinned.py --nam-repo nam-files --ucd-zip UCD-18.0.0.zip --ucd-dir ucd-18.0.0 --check
```

The first check proves original generated files are reproducible; the last check
proves the proposed outputs. Inspect `git diff --check` and the small NAM diff.
Paths in these example commands are placeholders that must be resolved for the
new checkout; they are not dependencies on the author's machine.
The NAM diff is compressed only for artifact storage: expand it to a task-local
file and pass that actual file's absolute path to git apply. Its standard patch
context and whitespace are preserved. Bulk browser JSON/manifests and native
log copies are also gzip-compressed; local test generation writes normal files.

## 2. Actual Cargo override and executable

```sh
git -C fontspector apply /ABSOLUTE/PATH/patches/fontspector-local-nam.patch
cargo test --manifest-path nam-files/Cargo.toml --locked --test nambli_marks
cargo metadata --manifest-path fontspector/Cargo.toml --locked --format-version 1 > cargo-metadata.json
cargo tree --manifest-path fontspector/Cargo.toml --locked -i google-fonts-subsets
cargo build --manifest-path fontspector/Cargo.toml --locked --release -p fontspector
```

Inspect metadata, not just the TOML line: google-fonts-subsets **0.202602.1** must
have `source: null` and a manifest path in `nam-files`; languages **0.7.11** must
remain a registry package. Confirm no check/language files or other lock entries
were changed. Record the built tool's version and SHA-256. The tested build used
Rust/cargo 1.98.0 and a task-local Cargo cache/target directory. The four Rust
regression tests pass; the unchanged published crate does not satisfy them.

On Windows use the installed MSVC build-tools environment. A freetype-sys 0.23.0
build needed the compiler include flag for libz-sys 1.1.29's existing zlib
headers (`CFLAGS=/I<TASK_CARGO_CACHE>/registry/src/<registry-id>/libz-sys-1.1.29/src/zlib`).
This is a process-only build flag; neither crate source nor Windows security
settings were modified. Host-appropriate toolchain setup is required; a Linux
binary will have a different executable hash.

## 3. Full unsuppressed profiles and strict runner tests

```sh
python -m unittest discover -s sources -p test_run_qa.py -v
python sources/run_qa.py --scope package --family ORIGINAL_PACKAGE/ofl/nambli --executable STOCK_EXECUTABLE --output qa-original-stock --mode network --tool-kind stock
python sources/run_qa.py --scope package --family ORIGINAL_PACKAGE/ofl/nambli --executable PATCHED_EXECUTABLE --output qa-original-patched --mode network --tool-kind patched-candidate
python sources/run_qa.py --scope package --family FINAL_PACKAGE/ofl/nambli --executable STOCK_EXECUTABLE --output qa-final-stock --mode network --tool-kind stock
python sources/run_qa.py --scope package --family FINAL_PACKAGE/ofl/nambli --executable PATCHED_EXECUTABLE --output qa-final-patched --mode network --tool-kind patched-candidate
```

Stock is expected to exit 1 with sixteen missing-subsetted messages. The local
patched runs exit 0, with tofu executed. The runner preserves raw JSON/logs,
exact native exit code, version, executable SHA and before/final input SHA.
WARN are not removed. Use `--mode offline` only in a separate explicitly offline
run; it is not a substitute for network QA. `NAMBLI_QA_TMPDIR` can point to a
writable scratch directory on restricted Windows hosts. CI runs the nine runner
regression tests; it does not falsely advertise a stock full-package PASS.

## 4. Real WOFF2, all faces and available browsers

Download/extract the original published subset crate
https://static.crates.io/crates/google-fonts-subsets/google-fonts-subsets-0.202602.1.crate
and verify its SHA-256 from REPORT.md. Pass its **Lib/gfsubsets/data** directory
as the baseline. Corpus is the unchanged pinned language content in this dated
evidence directory, including all 16 exact failing texts and controls:

```sh
python sources/qa_subsets.py --family ORIGINAL_PACKAGE/ofl/nambli --baseline-nam PUBLISHED_CRATE/Lib/gfsubsets/data --patched-nam nam-files/Lib/gfsubsets/data --corpus documentation/google-fonts-qa/2026-10-07/corpus.json --output subset-fixture
node sources/run_browser_qa.cjs --fixture subset-fixture --output browser-results --playwright-module /PATH/TO/playwright --chromium-executable /PATH/TO/chromium --webkit-executable /PATH/TO/webkit
```

Use Playwright 1.62.1 in a task-local npm directory. Browser executable flags
are optional where its usual browser cache works; `--firefox-executable` is also
supported. Run existing browsers or obtain appropriate task-local browsers in
your own test environment. No global installation is required by the scripts.
Missing engines are recorded NOT TESTED. The tested host had Chromium and
Playwright WebKit for Windows; Firefox and real Safari/iOS were unavailable.
The runner uses dedicated temporary profiles and a loopback HTTP server, loads
actual WOFF2, waits for fonts.ready, captures diagnostics/screenshots and compares
pixels/advances for all styles. Merely calling fonts.check is not proof.

Expected native results: 12 faces / 180 WOFF2 / 576 whole-text checks / 1,284
minimal clusters / 11,640 encoded-character checks. Coherent has zero mismatched
clusters; literal NAM still has 24. Each tested engine has 576 text comparisons,
zero coherent differences, and actual stock/literal differences preserved.
This is a local serving model, not a reproduction of the private Google backend.

Serve `subset-fixture` with a local HTTP server to interact with
`Nambli-Subset-Review.html`; file:// does not supply the fixture's JSON fetch.

## 5. Approved build and separate visual candidate

```sh
python sources/build_fontmake.py --output build-approved --reference-fonts fonts/ttf --verify-reproducible
```

Only the isolated `codex/fix/google-fonts-outline-candidate` branch changes UFO
contours/version to 1.001. Its guarded preparation script reads the approved
1.000 sources/reference fonts; see that branch's CANDIDATE.md. Do not apply it to
release sources, push those binaries to Google PR #11086 or update the site.

```sh
python sources/build_fontmake.py --output build-outline-candidate --verify-reproducible
python sources/validate_outline_candidate.py --baseline APPROVED_TTF --candidate build-outline-candidate --output candidate-audit.json
python sources/make_outline_qa_review.py --baseline APPROVED_TTF --candidate build-outline-candidate --output candidate-review
```

The audit permits exactly the eight documented glyph/face pairs and 1.001 name/
version strings, requires all other normalized outlines, metrics, cmap, layout,
kerning and shaping unchanged, and verifies candidate WOFF2 tables. The standalone
review HTML embeds genuine outlines and the 48 unchanged side-caron controls.
Candidate OTF reproduction is not claimed. Keep its binary QA scope distinct
from the 1.000 full-package results.
