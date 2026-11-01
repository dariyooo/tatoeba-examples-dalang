# tatoeba-examples-dalang

Example sentences from the [Tatoeba](https://tatoeba.org) corpus, one dictionary per language.

Every sentence comes with the group ids of its translations (the sentences of other languages it is linked to),
links to its audio recordings, its review score and the self-reported skill of its author in the language.
Duplicates (the same sentence after NFKC normalization) are merged.

These are example dictionaries (`dakanji-examples`), they do not work in Yomitan.

## Assets

Released weekly for the 25 languages with the most sentences and Japanese, Mandarin and Korean:

| Asset | Content |
|---|---|
| `tatoeba-examples-dalang-{lang}.zip` | all sentences of `{lang}` |
| `tatoeba-examples-dalang-{lang}-main-{main}.zip` | only the sentences of `{lang}` with a translation to `{main}` (`jpn`, `cmn`, `kor`) |

`{lang}` is the ISO 639-3 code Tatoeba uses, e.g. `eng`, `jpn`.
The `-main-` variants are for learners of the main language, e.g. `tatoeba-examples-dalang-eng-main-jpn` holds the
English sentences that have a Japanese translation.

## Sources

The Tatoeba [exports](https://downloads.tatoeba.org/exports/), locked to their download date in `sources.lock.json`:
`sentences_detailed`, `links`, `sentences_with_audio`, `user_languages` and `users_sentences`.
Tatoeba updates them weekly, the *Update* workflow picks them up and releases on changes.

## Installation

Make sure [uv](https://github.com/astral-sh/uv) is installed on your system and run

``` bash
uv sync
```

## Usage

``` bash
uv run build.py
```

This downloads the exports to `tmp/sources/` and creates the dictionaries in `out/`
(`.zip`, `.index.json` and `.manifest.json` each). The uncompressed dictionaries are kept in `tmp/` for inspection.

## Development

``` bash
uv run ruff check .          # lint
uv run ruff format .         # format
uv run pyright               # type check
uv run pytest                # tests
```

The tests run the pipeline on a subset of the exports in `tests/data/`.

The repo follows the [DaLang dictionary repo standard](https://github.com/dariyooo/dalang-dict-utils/blob/main/docs/repo-standard.md),
update the shared setup with `uvx copier update --trust`.

## Release

The *Update* workflow releases weekly when the sources changed. To release by hand, push a tag with today's date:

``` bash
git tag 2026-11-01 && git push origin 2026-11-01
```

The *Release* workflow runs the checks, builds the dictionaries with the tag as revision and publishes them as the GitHub release of the tag.
To redo a release, push the tag again with `git tag -f 2026-11-01 && git push -f origin 2026-11-01`.
Tatoeba replaces its exports in place, so once it published new ones a tag release fails on the locked sha256,
run the *Update* workflow then.
Installed dictionaries pick up new releases through "Check for updates".

## License

Sentences and translations by the [Tatoeba](https://tatoeba.org) contributors,
[CC BY 2.0 FR](https://creativecommons.org/licenses/by/2.0/fr/). Audio recordings keep the license of their recording.
