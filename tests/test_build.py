from tatoeba_examples.build import INDEX_FIELDS, build_index_fields, languages, package_name


def test_index_has_required_fields():
    for field in ("author", "url", "attribution"):
        assert field in INDEX_FIELDS
    assert {"title", "sourceLanguage", "description"} <= set(build_index_fields("eng", None))


def test_languages_are_the_top_languages_and_the_main_languages():
    counts = {"eng": 3, "jpn": 2, "deu": 2, "cmn": 1, "kor": 1}
    assert languages(counts, n=2) == ["eng", "deu", "jpn", "cmn", "kor"]


def test_variants_have_their_own_names_and_titles():
    assert package_name("eng", None) == "tatoeba-examples-dalang-eng"
    assert package_name("eng", "jpn") == "tatoeba-examples-dalang-eng-main-jpn"
    assert build_index_fields("eng", None)["title"] == "Tatoeba Examples (eng)"
    assert build_index_fields("eng", "jpn")["title"] == "Tatoeba Examples (eng, with jpn translations)"
