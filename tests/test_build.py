from tatoeba_examples.build import INDEX_FIELDS


def test_index_has_required_fields():
    for field in ("author", "url", "description", "attribution"):
        assert field in INDEX_FIELDS
