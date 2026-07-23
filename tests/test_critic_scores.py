from enrich.critic_scores import extract_critic_scores, best_critic_score


def _scores(text):
    return {(d["critic"], d["score"]) for d in extract_critic_scores(text)}


def test_named_critic_codes():
    assert _scores("Great wine. JS 95, WS 92") == {("JS", 95), ("WS", 92)}


def test_full_critic_names():
    out = _scores("James Suckling 94 points; Robert Parker 93")
    assert ("JS", 94) in out
    assert ("RP", 93) in out


def test_points_marker_without_critic():
    assert _scores("Rated 92 points") == {("points", 92)}


def test_slash_100():
    assert _scores("Scored 93/100 by critics") == {("points", 93)}


def test_range_takes_upper_bound():
    assert ("WA", 95) in _scores("WA 93-95")


def test_year_is_not_a_score():
    assert _scores("Penfolds Bin 389 2021") == set()


def test_size_is_not_a_score():
    assert _scores("Big bottle 750ml") == set()


def test_scores_out_of_range_filtered():
    # 70 is below the critic floor, 105 impossible
    assert _scores("only 70 points here") == set()


def test_dedupe_repeated():
    assert _scores("JS 95 ... JS 95 again") == {("JS", 95)}


def test_empty_text():
    assert extract_critic_scores("") == []
    assert extract_critic_scores(None) == []


def test_best_critic_score_returns_max():
    assert best_critic_score([{"critic": "JS", "score": 92},
                              {"critic": "WA", "score": 96}]) == 96


def test_best_critic_score_none_when_empty():
    assert best_critic_score([]) is None
