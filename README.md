# Nambli

Nambli is a rounded display font family with Latin and Cyrillic coverage,
developed under the creative direction of **Yurii Tor**, with AI-assisted
outline programming and engineering.

![Nambli family specimen](documentation/specimen.png)

Six weights — Light, Regular, Medium, SemiBold, Bold and ExtraBold — each have
an italic companion. The family is intended for branding, headings and short
text. This development branch contains a 1.000 technical candidate for review;
the published v0.7.4 release remains available separately.
The candidate contains 970 encoded characters and 998 glyphs per style.

## Download and use

Download the ZIP from [Releases](https://github.com/Tor-Production/nambli-font/releases).
Install TTF or OTF files, not both formats simultaneously. WOFF2 is provided
for self-hosted websites. Font files are in `fonts/ttf`, `fonts/otf` and
`fonts/webfonts`.

## License and attribution

The font software and original project sources are offered under the
[SIL Open Font License 1.1](OFL.txt), without a Reserved Font Name.
Commercial design use, embedding, modification and redistribution are allowed
under the license. The font may not be sold by itself; bundling with other
software is permitted. This does not license unrelated Nambli branding assets.
Yurii Tor is listed in [AUTHORS.txt](AUTHORS.txt).

See [provenance](documentation/PROVENANCE.txt) for the role of AI tools and
the human contribution. No government registration or judicial determination
of authorship is claimed by this repository.

## Source and build

The twelve editable UFO3 masters in `sources/ufos` include the complete candidate
outlines, metrics, Unicode mapping, kerning and OpenType feature source. Build
them with the pinned Fontmake toolchain:

Install Python and the packages in `requirements.txt`, then run:

```sh
python -m pip install -r requirements.txt
python sources/build_fontmake.py
```

The build writes TTF and WOFF2 files into `build-fonts/`, validates them against
their editable sources, and leaves committed font files untouched. See
[building and validation instructions](sources/BUILDING.md) for the repeat-build
check and the distinction between the current production pipeline and historical
construction scripts. The latter remain in `sources/`, with the historical
master in `sources/master`.

## Google Fonts status

**Not yet included in Google Fonts.** The family was submitted in
[google/fonts#11082](https://github.com/google/fonts/issues/11082). Yurii Tor's
Individual CLA was verified on 2026-10-07. Submission and a signed CLA do not
establish curatorial acceptance.

The 1.000 candidate adds required characters and language support, corrects
layout and outline defects, and supplies a reproducible production build.
New and changed designs still need visual review. Detailed results and remaining
findings are recorded in [Google Fonts status](documentation/GOOGLE-FONTS-STATUS.txt).
