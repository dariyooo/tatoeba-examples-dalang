from dalang_dict import GitHubFile, build_index, fetch, package_dictionary

GITHUB_REPO = "dariyooo/tatoeba-examples-dalang"
ASSET = "tatoeba-examples-dalang"
TITLE = "tatoeba-examples-dalang"

# Locked to a version in sources.lock.json, updated by the Update workflow.
# `used_for` and the version are listed in the release notes.
SOURCE = GitHubFile("source.json", repo="owner/repo", path="path/to/source.json", used_for="")

INDEX_FIELDS = {
    "author": "",
    "url": f"https://github.com/{GITHUB_REPO}",
    "description": "Example sentences from the Tatoeba corpus",
    "attribution": "",
}


def build_banks(source: object) -> dict[str, list]:
    """Converts the source data to bank entries, e.g. {"kanji_bank": [...]}."""
    raise NotImplementedError


def main() -> None:
    banks = build_banks(fetch(SOURCE))
    index = build_index(TITLE, GITHUB_REPO, ASSET, **INDEX_FIELDS)
    package_dictionary(ASSET, index, banks)
