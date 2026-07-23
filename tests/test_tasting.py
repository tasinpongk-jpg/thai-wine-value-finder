from enrich.tasting import parse_sections


def test_parses_labeled_prose():
    text = ("Appearance : Deep ruby with violet hints. "
            "Aroma : Blackberry, cassis and graphite. "
            "Palate : Velvety tannins, long finish.")
    out = parse_sections(text)
    assert out["appearance"] == "Deep ruby with violet hints"
    assert out["nose"] == "Blackberry, cassis and graphite"
    assert out["palate"] == "Velvety tannins, long finish"


def test_maps_synonyms_to_canonical_keys():
    out = parse_sections("Nose : citrus. Taste : crisp. Colour : pale gold.")
    assert out["nose"] == "citrus"
    assert out["palate"] == "crisp"
    assert out["appearance"] == "pale gold"


def test_ignores_unknown_labels():
    out = parse_sections("Variety : 90% Cabernet. Appearance : garnet.")
    assert "appearance" in out
    assert out["appearance"] == "garnet"
    assert "variety" not in out


def test_pairing_extracted():
    out = parse_sections("Pairing : Best with grilled meats and aged cheese.")
    assert out["pairing"] == "Best with grilled meats and aged cheese"


def test_empty_and_unlabeled():
    assert parse_sections("") == {}
    assert parse_sections("Just a plain sentence with no labels.") == {}
