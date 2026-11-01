"""Build DaKanji example-sentence banks from the Tatoeba corpus.

Each primary P emits ``groupIds(P) = {P} ∪ {primary(n) for n a direct
cross-lang neighbour}``. 1-hop only, no transitive closure — union-find
collapsed 12k+ unrelated sentences into one cluster.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tarfile
import unicodedata
from array import array
from collections import defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path

CHUNK_SIZE = 25_000


# --- I/O ---


def stream_tar_bz2(filename: str) -> Iterator[str]:
    with tarfile.open(filename, "r:bz2") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            handle = tar.extractfile(member)
            if handle is None:
                continue
            for line in io.TextIOWrapper(handle, encoding="utf-8"):
                yield line.rstrip("\n")


# --- Parsers (one per Tatoeba export) ---


def parse_user_skills(tmp_dir: str) -> dict[tuple[str, str], str]:
    print("1. Parsing user skills...")
    skills: dict[tuple[str, str], str] = {}
    for line in stream_tar_bz2(os.path.join(tmp_dir, "user_languages.tar.bz2")):
        parts = line.split("\t")
        if len(parts) >= 3:
            skills[(parts[2], parts[0])] = parts[1]
    return skills


def parse_user_reviews(tmp_dir: str) -> dict[int, int]:
    print("2. Parsing user reviews...")
    revs: dict[int, int] = defaultdict(int)
    with open(os.path.join(tmp_dir, "users_sentences.csv"), encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3:
                revs[int(parts[1])] += int(parts[2])
    return revs


def check_bad_tag(tag: str) -> bool:
    # Filter long debug-style tags and ``by <user>`` attribution noise.
    if len(tag) > 30:
        return False
    if tag.lower().startswith("by "):
        return False
    return True


def parse_tags(tmp_dir: str) -> tuple[dict[int, list[str]], set[str]]:
    print("3. Parsing sentence tags (Optional)...")
    s_tags: dict[int, list[str]] = defaultdict(list)
    unique: set[str] = set()
    fname = os.path.join(tmp_dir, "tags.tar.bz2")
    if not os.path.exists(fname):
        return s_tags, unique

    for line in stream_tar_bz2(fname):
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        sid, tname = int(parts[0]), parts[1].strip()
        if not check_bad_tag(tname):
            continue
        if tname not in s_tags[sid]:
            s_tags[sid].append(tname)
        unique.add(tname)
    return s_tags, unique


def parse_audio_meta(tmp_dir: str) -> tuple[dict[int, list[dict]], set[str], set[str]]:
    print("4. Parsing audio metadata...")
    s_audio: dict[int, list[dict]] = defaultdict(list)
    creators: set[str] = set()
    licenses: set[str] = set()
    for line in stream_tar_bz2(os.path.join(tmp_dir, "sentences_with_audio.tar.bz2")):
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        sid = int(parts[0])
        user = parts[2] if len(parts) > 2 else ""
        lic = parts[3] if len(parts) > 3 else ""
        s_audio[sid].append({"id": parts[1], "user": user, "lic": lic})
        if user:
            creators.add(user)
        if lic:
            licenses.add(lic)
    return s_audio, creators, licenses


class LinkGraph:
    """CSR adjacency over sentence ids.

    A dict-of-sets for the ~28M Tatoeba link rows peaks at ~6GB and OOMs the
    16GB CI runner; flat arrays hold the same graph in about 1GB.
    Neighbour lists may contain duplicates (the export lists both
    directions) — callers already collect into sets.
    """

    _EMPTY = array("i")

    def __init__(self, offsets: array, neighbors: array, max_sid: int) -> None:
        self._offsets = offsets
        self._neighbors = neighbors
        self._max_sid = max_sid

    def neighbors(self, sid: int) -> array:
        if 0 <= sid <= self._max_sid:
            return self._neighbors[self._offsets[sid] : self._offsets[sid + 1]]
        return self._EMPTY


def build_direct_links(tmp_dir: str) -> LinkGraph:
    print("5. Mapping direct translations...")
    # 'i' (int32) is fine: Tatoeba sids are ~13M, far below 2**31.
    src = array("i")
    dst = array("i")
    max_sid = -1
    for line in stream_tar_bz2(os.path.join(tmp_dir, "links.tar.bz2")):
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        try:
            u, v = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        src.append(u)
        dst.append(v)
        if u > max_sid:
            max_sid = u
        if v > max_sid:
            max_sid = v

    n = max_sid + 1
    offsets = array("q", [0]) * (n + 1)
    for u in src:
        offsets[u + 1] += 1
    for v in dst:
        offsets[v + 1] += 1
    for i in range(1, n + 1):
        offsets[i] += offsets[i - 1]

    neighbors = array("i", [0]) * (2 * len(src))
    cursor = array("q", offsets[:n])
    for u, v in zip(src, dst, strict=True):
        cu = cursor[u]
        neighbors[cu] = v
        cursor[u] = cu + 1
        cv = cursor[v]
        neighbors[cv] = u
        cursor[v] = cv + 1
    return LinkGraph(offsets, neighbors, max_sid)


def count_languages(tmp_dir: str) -> dict[str, int]:
    # Pre-pass for --top.
    print("0. Counting sentences per language for top-N selection...")
    counts: dict[str, int] = defaultdict(int)
    for line in stream_tar_bz2(os.path.join(tmp_dir, "sentences_detailed.tar.bz2")):
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        lang = parts[1]
        if lang == r"\N":
            continue
        counts[lang] += 1
    return counts


# --- Engine ---


def _build_tag_bank(unique_tags: Iterable[str], licenses: Iterable[str], creators: Iterable[str]) -> list[list]:
    bank: list[list] = []
    bank.extend([t, "sentence_tag", 1, f"Tatoeba: {t}", 0] for t in sorted(unique_tags))
    bank.extend([lic, "audio_license", 2, f"License: {lic}", 0] for lic in sorted(licenses))
    bank.extend([c, "audio_creator", 3, f"Voice: {c}", 0] for c in sorted(creators))
    return bank


def run_pipeline(
    target_langs: list[str] | None, main_lang: str | None, include_tags: bool, tmp_dir: str, out_dir: str
) -> dict[str, Path]:
    """Writes the tag and example banks of every language in `target_langs` (all if None) to `out_dir/dict_{lang}/`.

    `tmp_dir` holds the Tatoeba exports. Returns the bank folder of each language.
    """
    os.makedirs(out_dir, exist_ok=True)

    skills = parse_user_skills(tmp_dir)
    reviews = parse_user_reviews(tmp_dir)
    sentence_tags, unique_tags = parse_tags(tmp_dir) if include_tags else ({}, set())
    audio_meta, creators, licenses = parse_audio_meta(tmp_dir)

    allowed_langs: set[str] = set(target_langs) if target_langs else set()
    if main_lang:
        allowed_langs.add(main_lang)

    links = build_direct_links(tmp_dir)

    # --- 1. Sentence dedup ---
    # NFKC collapses width/whitespace variants Tatoeba stores separately.
    print("6. Loading language map and deduplicating sentences...")
    sid_to_lang: dict[int, str] = {}
    sid_to_primary: dict[int, int] = {}
    primary_to_sids: dict[int, list[int]] = defaultdict(list)
    primary_info: dict[int, tuple[str, str]] = {}
    text_to_primary: dict[tuple[str, str], int] = {}

    for line in stream_tar_bz2(os.path.join(tmp_dir, "sentences_detailed.tar.bz2")):
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        lang = parts[1]
        if lang == r"\N":
            continue
        # Nothing downstream ever asks for the lang of a filtered-out sid, so
        # skipping them here keeps sid_to_lang proportional to allowed_langs.
        if allowed_langs and lang not in allowed_langs:
            continue
        sid, text = int(parts[0]), parts[2].strip()
        lang = sys.intern(lang)

        key = (lang, unicodedata.normalize("NFKC", text))
        primary = text_to_primary.setdefault(key, sid)
        sid_to_lang[sid] = lang
        primary_to_sids[primary].append(sid)
        if primary == sid:
            primary_info[sid] = (text, sys.intern(parts[3]))
        sid_to_primary[sid] = primary

    del text_to_primary  # normalized-text keys dominate this pass's memory

    tag_bank = _build_tag_bank(unique_tags, licenses, creators)

    # --- 2. Group, filter and emit in one streaming pass ---
    # Per-sentence groupIds (1-hop, no transitive merge), computed per primary
    # so the full primary→group map never has to be held in memory at once.
    print("7. Computing translation groups and generating language chunks...")
    lang_states: dict[str, dict] = {}
    total_processed = 0

    for primary in sorted(primary_to_sids):
        lang = sid_to_lang[primary]
        if target_langs and lang not in target_langs:
            continue

        group_ids = {primary}
        for sid in primary_to_sids[primary]:
            for nb in links.neighbors(sid):
                np = sid_to_primary.get(nb)
                if np is not None and sid_to_lang[np] != lang:
                    group_ids.add(np)

        # Secondary-lang sentences must have at least one direct main_lang
        # link; otherwise the dict would carry entries with no main-lang
        # counterpart.
        if main_lang and lang != main_lang:
            if not any(sid_to_lang.get(g) == main_lang for g in group_ids):
                continue

        text, user = primary_info[primary]

        state = lang_states.get(lang)
        if state is None:
            l_dir = os.path.join(out_dir, f"dict_{lang}")
            os.makedirs(l_dir, exist_ok=True)
            with open(os.path.join(l_dir, "tag_bank_1.json"), "w", encoding="utf-8") as f:
                json.dump(tag_bank, f, ensure_ascii=False)
            chunk = open(os.path.join(l_dir, "example_bank_1.json"), "w", encoding="utf-8")
            chunk.write("[\n")
            state = lang_states[lang] = {"f": chunk, "count": 0, "total": 0, "idx": 1, "dir": l_dir, "first": True}

        if state["count"] >= CHUNK_SIZE:
            state["f"].write("\n]\n")
            state["f"].close()
            state["idx"] += 1
            state["count"] = 0
            state["first"] = True
            state["f"] = open(os.path.join(state["dir"], f"example_bank_{state['idx']}.json"), "w", encoding="utf-8")
            state["f"].write("[\n")

        merged_sids = primary_to_sids[primary]
        # .get keeps the defaultdict from materialising an entry per queried sid.
        total_review = sum(reviews.get(s, 0) for s in merged_sids)
        merged_tags: set[str] = set()
        for s in merged_sids:
            merged_tags.update(sentence_tags.get(s, []))

        merged_audio = []
        for s in merged_sids:
            for a in audio_meta.get(s, []):
                a_tags = [t for t in (a["user"], a["lic"]) if t]
                merged_audio.append(
                    {
                        "source": f"https://tatoeba.org/audio/download/{a['id']}",
                        "tags": list(dict.fromkeys(a_tags)),  # ordered dedupe
                    }
                )

        stats: list[dict] = []
        if total_review:
            stats.append({"statName": "review_score", "value": total_review})
        sk = skills.get((user, lang))
        if sk:
            value = int(sk) if sk.isdigit() else 0
            entry = {"statName": "user_skill", "value": value}
            if str(value) != str(sk):
                entry["displayValue"] = str(sk)  # preserve non-numeric self-reports (e.g. "\N")
            stats.append(entry)

        obj = {
            "groupIds": sorted(group_ids),
            "sentence": text,
            "tags": sorted(merged_tags),
            "stats": stats,
            "audios": merged_audio,
        }

        if not state["first"]:
            state["f"].write(",\n")
        state["f"].write("  " + json.dumps(obj, ensure_ascii=False))
        state["first"] = False
        state["count"] += 1
        state["total"] += 1
        total_processed += 1
        if total_processed % 100_000 == 0:
            print(f"   ... Processed {total_processed} primary sentences")

    del links, sid_to_lang, sid_to_primary, primary_to_sids, primary_info

    lang_dirs: dict[str, Path] = {}
    for lang, state in sorted(lang_states.items()):
        state["f"].write("\n]\n")
        state["f"].close()
        lang_dirs[lang] = Path(state["dir"])
    return lang_dirs
