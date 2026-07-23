from enrich.cellar import drink_window


def test_full_red_window_and_ready():
    w = drink_window(2020, "Red", "Full-Bodied", now_year=2026)
    assert w["start"] == 2022
    assert w["end"] == 2032
    assert w["status"] == "Ready"


def test_light_white_shorter_window():
    w = drink_window(2024, "White", None, now_year=2026)
    assert w["start"] == 2025
    assert w["end"] == 2028
    assert w["status"] == "Ready"


def test_red_past_peak():
    w = drink_window(2008, "Red", None, now_year=2026)
    assert w["status"] == "Past peak"


def test_young_red_on_hold():
    w = drink_window(2025, "Red", "Full-Bodied", now_year=2026)
    # start = 2027 -> still on hold in 2026
    assert w["start"] == 2027
    assert w["status"] == "Hold"


def test_sparkling_window():
    w = drink_window(2022, "Sparkling", None, now_year=2026)
    assert w["start"] == 2022
    assert w["status"] == "Ready"


def test_no_vintage_ready_now():
    w = drink_window(None, "Sparkling", None, now_year=2026)
    assert w["start"] is None
    assert w["status"] == "Ready now"


def test_label_formats_a_range():
    w = drink_window(2020, "Red", "Full-Bodied", now_year=2026)
    assert w["label"] == "2022–2032"
    assert drink_window(None, "Red", None, now_year=2026)["label"] == "Anytime"
