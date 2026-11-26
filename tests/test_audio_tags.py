import io
import tarfile

from tatoeba_examples.pipeline import _build_tag_bank, parse_audio_meta


def _write_export(tmp_path, rows: list[str]) -> None:
    data = "".join(f"{row}\n" for row in rows).encode()
    with tarfile.open(tmp_path / "sentences_with_audio.tar.bz2", "w:bz2") as tar:
        info = tarfile.TarInfo("sentences_with_audio.csv")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))


def test_null_speaker_and_license_are_left_out(tmp_path):
    _write_export(
        tmp_path,
        [
            "1\t101\tCK\tCC BY 4.0\t",
            "2\t102\tLeviHighway\t\t",
            "3\t103\t\\N\t\\N\t\\N",
        ],
    )
    audio, creators, licenses = parse_audio_meta(str(tmp_path))

    assert creators == {"CK", "LeviHighway"}
    assert licenses == {"CC BY 4.0"}
    assert audio[3] == [{"id": "103", "user": "", "lic": ""}]


def test_audio_credit_categories_are_hidden():
    bank = _build_tag_bank(["idiom"], ["CC BY 4.0"], ["CK"])
    assert bank == [
        ["idiom", "sentence_tag", 1, "Tatoeba: idiom", 0],
        ["CC BY 4.0", ".audio_license", 2, "License: CC BY 4.0", 0],
        ["CK", ".audio_creator", 3, "Voice: CK", 0],
    ]
