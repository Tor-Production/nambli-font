# Nambli

Nambli is a rounded display font family with Latin and Cyrillic coverage,
developed under the creative direction of **Yurii Tor**, with AI-assisted
outline programming and engineering.

![Nambli family specimen](documentation/specimen.png)

Six weights — Light, Regular, Medium, SemiBold, Bold and ExtraBold — each have
an italic companion. Each of the 12 styles has 872 encoded characters and
887 glyphs. The family is intended for branding, headings and short text.

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

The original parametric sources are in `sources/`, with the historical approved
master in `sources/master`. The 12 approved faces also have editable UFO3
snapshots in `sources/ufos`, including OpenType feature source. Their outline,
metric, Unicode and shaping round trips have been validated; see
[the validation report](documentation/ufo-validation.json).

Install Python and the packages in `requirements.txt`, then run:

```sh
python -m pip install -r requirements.txt
bash sources/build.sh
```

The historical design generator writes into `build-fonts/`, and its UFO export
and validation write into `build-ufos/`, keeping the shipping files separate.
On Windows without Bash, run `python sources/build_family.py` and then
`python sources/export_ufo.py --fonts build-fonts --output build-ufos`.
The Regular TTF/OTF rebuild exactly preserves the approved outlines, metrics,
Unicode mapping and shaping tables, with 130,608 shaping comparisons and no
differences. See [the scoped build audit](documentation/regular-build-validation.json).
The full 12-style production rebuild remains to be revalidated. The committed
UFO snapshots preserve the shipping design; a fontmake pipeline is not claimed.

## Google Fonts status

**Not yet included in Google Fonts.** This first public OFL package preserves
the approved 0.7.3 design and adds licensing metadata as version 0.704.
Google Fonts preparation is tracked in [known issues](documentation/GOOGLE-FONTS-STATUS.txt).
No claim is made that the Google Fonts profile currently passes.
