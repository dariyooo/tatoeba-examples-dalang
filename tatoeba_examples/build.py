"""Builds the Tatoeba example dictionaries: one per language, plus variants that only keep sentences translated
to a main language."""

import shutil
from pathlib import Path

from dalang_dict import Url, build_index, fetch, package_dictionary

from tatoeba_examples.pipeline import count_languages, run_pipeline

GITHUB_REPO = "dariyooo/tatoeba-examples-dalang"
ASSET = "tatoeba-examples-dalang"
TITLE = "Tatoeba Examples"

EXPORTS_URL = "https://downloads.tatoeba.org/exports/"
# Locked to their download date and sha256 in sources.lock.json, updated by the Update workflow.
# `used_for` and the version are listed in the release notes.
SOURCES = [
    Url(
        "sentences_detailed.tar.bz2", EXPORTS_URL + "sentences_detailed.tar.bz2", used_for="sentences and their authors"
    ),
    Url("links.tar.bz2", EXPORTS_URL + "links.tar.bz2", used_for="translations, as group ids"),
    Url("sentences_with_audio.tar.bz2", EXPORTS_URL + "sentences_with_audio.tar.bz2", used_for="audio links"),
    Url("user_languages.tar.bz2", EXPORTS_URL + "user_languages.tar.bz2", used_for="author skill (`user_skill`)"),
    Url("users_sentences.csv", EXPORTS_URL + "users_sentences.csv", used_for="sentence reviews (`review_score`)"),
]
TOP_LANGUAGES = 25
# Variants for learners of these languages: every language, but only sentences with a translation to the main language
MAIN_LANGUAGES = ["jpn", "cmn", "kor"]

BANKS_DIR = Path("tmp") / "banks"

INDEX_FIELDS = {
    "author": "Tatoeba.org Contributors",
    "url": "https://tatoeba.org",
    "attribution": "Creative Commons Attribution 2.0 France (CC-BY 2.0 FR)",
}


def languages(counts: dict[str, int], n: int = TOP_LANGUAGES) -> list[str]:
    """The `n` languages with the most sentences and the main languages."""
    top = sorted(counts, key=lambda lang: (-counts[lang], lang))[:n]
    return top + [lang for lang in MAIN_LANGUAGES if lang not in top]


def package_name(lang: str, main_lang: str | None) -> str:
    return f"{ASSET}-{lang}" + (f"-main-{main_lang}" if main_lang else "")


def build_index_fields(lang: str, main_lang: str | None) -> dict:
    title = f"{TITLE} ({lang}" + (f", with {main_lang} translations)" if main_lang else ")")
    description = (
        f"Example sentences in {lang} from the Tatoeba Project, with their translations, audio links, "
        "reviews and the skill of their authors."
    )
    if main_lang:
        description += f" Only sentences with a {main_lang} translation."
    return {"title": title, "sourceLanguage": lang, "description": description, **INDEX_FIELDS}


def main() -> None:
    # fetch() caches the exports by name in tmp/sources/, where the pipeline reads them from
    data_dir = str([fetch(source) for source in SOURCES][0].parent)
    langs = languages(count_languages(data_dir))
    print(f"Languages: {', '.join(langs)}")

    for main_lang in [None, *MAIN_LANGUAGES]:
        banks_dir = BANKS_DIR / (main_lang or "all")
        shutil.rmtree(banks_dir, ignore_errors=True)
        lang_dirs = run_pipeline(langs, main_lang, False, data_dir, str(banks_dir))
        # A variant's main language keeps all its sentences, it is the same as the dictionary without main language
        if main_lang:
            lang_dirs.pop(main_lang, None)
        for lang, lang_dir in lang_dirs.items():
            name = package_name(lang, main_lang)
            fields = build_index_fields(lang, main_lang)
            index = build_index(fields.pop("title"), GITHUB_REPO, name, **fields)
            banks = {path.name: path for path in sorted(lang_dir.iterdir())}
            package_dictionary(name, index, {}, extra_files=banks, format="dakanji-examples")
        # The packaged banks are hard links to these, removing them only tidies tmp/
        shutil.rmtree(banks_dir)
