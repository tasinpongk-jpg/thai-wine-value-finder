from enrich import normalize as N


# ---- price -------------------------------------------------------------
def test_woocommerce_satang_price_divides_by_100():
    # WooCommerce stores "459000" satang with minor_unit 2 -> 4590.00 baht
    assert N.parse_wc_price("459000", 2) == 4590.0


def test_woocommerce_price_minor_unit_zero():
    assert N.parse_wc_price("780", 0) == 780.0


def test_plain_price_string_with_commas():
    assert N.parse_price_text("฿1,159.00") == 1159.0


def test_plain_price_none_when_unparseable():
    assert N.parse_price_text("call for price") is None


# ---- size --------------------------------------------------------------
def test_size_ml_from_title():
    assert N.parse_size_ml("Chateau X 2019 - 750ml") == 750


def test_size_cl_converts_to_ml():
    assert N.parse_size_ml("Something (75cl)") == 750
    assert N.parse_size_ml("Magnum 150cl") == 1500


def test_size_litre_converts_to_ml():
    assert N.parse_size_ml("Big bottle 1.5L") == 1500


def test_size_defaults_none_when_absent():
    assert N.parse_size_ml("Just a wine name") is None


# ---- vintage -----------------------------------------------------------
def test_vintage_extracted_from_name():
    assert N.parse_vintage("Penfolds Bin 389 2021") == 2021


def test_vintage_nv_returns_none():
    assert N.parse_vintage("Champagne Brut (NV)") is None


def test_vintage_ignores_ml_numbers():
    # 750 must not be read as a year
    assert N.parse_vintage("Wine 750ml no year") is None


def test_vintage_out_of_range_ignored():
    assert N.parse_vintage("Lot 1872 reserve") is None


# ---- wine type ---------------------------------------------------------
def test_canonical_type_from_category():
    assert N.canonical_wine_type(["Reds", "France"]) == "Red"
    assert N.canonical_wine_type(["Champagne & Sparkling"]) == "Sparkling"
    assert N.canonical_wine_type(["White Wine"]) == "White"


def test_canonical_type_rose_unicode():
    assert N.canonical_wine_type(["Rosé"]) == "Rosé"


def test_canonical_type_from_thai_text():
    # winedutyfree embeds Thai colour words in the name
    assert N.canonical_wine_type([], text="ไวน์แดง อิตาลี") == "Red"
    assert N.canonical_wine_type([], text="ไวน์ขาว") == "White"


def test_canonical_type_defaults_other():
    assert N.canonical_wine_type(["Glassware"]) == "Other"


# ---- name normalization (for matching) --------------------------------
def test_normalize_name_lowercases_and_strips_size_vintage():
    a = N.normalize_name("Penfolds Bin 389 2021 - 750ml")
    b = N.normalize_name("penfolds  bin 389")
    assert a == b


def test_normalize_name_drops_punctuation():
    assert N.normalize_name("Château Haut-Brion!!") == N.normalize_name("chateau haut brion")


# ---- bottle size: Thai units + name beats attribute ------------------------
def test_parse_size_thai_units():
    assert N.parse_size_ml("ไวน์แดง 750 มล.") == 750
    assert N.parse_size_ml("ไวน์ขาว 375มล") == 375
    assert N.parse_size_ml("1.5 ลิตร") == 1500
    assert N.parse_size_ml("750 มิลลิลิตร") == 750


def test_parse_size_more_latin_units():
    assert N.parse_size_ml("Monte Antico 1.5 Ltr") == 1500
    assert N.parse_size_ml("Magnum 1500 ml.") == 1500
    assert N.parse_size_ml("750 ML") == 750


def test_parse_size_ignores_implausible_numbers():
    assert N.parse_size_ml("Pack of 0.5 ml samples") is None


def test_thai_size_stripped_from_vintage_and_matching_key():
    assert N.parse_vintage("ไวน์แดง 2000 มล.") is None
    assert N.normalize_name("Penfolds Bin 2 750 มล.") == N.normalize_name("Penfolds Bin 2")


def test_resolve_size_prefers_name_over_attribute():
    # Spirit House lists half bottles with a default "750 ml" attribute
    assert N.resolve_size_ml("Astoria Prosecco Extra Dry (375ml)", "750 ml") == 375
    assert N.resolve_size_ml("Monte Antico Magnum 1.5L", "750 ml") == 1500
    assert N.resolve_size_ml("Astoria Prosecco", "750 ml") == 750
    assert N.resolve_size_ml("Astoria Prosecco", None) is None


def test_parse_size_thousands_separator():
    # "1,500ml" must not be read as 500 ml
    assert N.parse_size_ml("Louis Perdrier Brut Rosé (1,500ml)") == 1500
    assert N.parse_size_ml("Big bottle 3,000 ml") == 3000
    assert N.parse_size_ml("Penfolds Bin 2, 750ml") == 750


def test_resolve_size_magnum_without_number():
    assert N.resolve_size_ml("Marques de Riscal Reserva Rioja Magnum", "750 ml") == 1500
    assert N.resolve_size_ml("Double Magnum 3L", "750 ml") == 3000


def test_safe_http_url_accepts_only_absolute_http_links():
    from enrich.normalize import safe_http_url
    ok = ["https://shop.example/wine?id=1", "http://shop.example/a b", "HTTPS://Shop.example/"]
    for url in ok:
        assert safe_http_url(url) == url
    assert safe_http_url("  https://x.example/w  ") == "https://x.example/w"
    bad = [None, "", "   ", "javascript:alert(1)", "JavaScript:alert(1)", " javascript:x",
           "data:text/html,<script>", "vbscript:x", "file:///etc/passwd", "ftp://x.example",
           "/relative/path", "//evil.example/x", "https://", "http:///nohost",
           "https://x.example/\njavascript:alert(1)", "java\tscript:alert(1)", float("nan")]
    for url in bad:
        assert safe_http_url(url) is None, url
