import yaml

from scraper.relevance_filter import is_excluded, passes_strong_filter, relevance_score


def test_shipped_keywords_exclude_known_irrelevant_terms():
    assert is_excluded("Open call for pottery makers")
    assert is_excluded("Ceramics residency in Cornwall")
    assert is_excluded("Education programme for schools")


def test_relevant_text_is_not_excluded():
    assert not is_excluded("Open call for new media art installation")
    assert not is_excluded(None)
    assert not is_excluded("")


def test_case_insensitive():
    assert is_excluded("POTTERY workshop")


def test_custom_config_is_user_definable(tmp_path):
    config_path = tmp_path / "exclude_keywords.yaml"
    config_path.write_text(yaml.safe_dump({"keywords": ["knitting"]}), encoding="utf-8")

    assert is_excluded("Knitting circle open call", config_path=config_path)
    assert not is_excluded("Pottery open call", config_path=config_path)  # not in this custom list


def test_empty_config_excludes_nothing(tmp_path):
    config_path = tmp_path / "exclude_keywords.yaml"
    config_path.write_text(yaml.safe_dump({"keywords": []}), encoding="utf-8")

    assert not is_excluded("Pottery open call", config_path=config_path)


def test_strong_filter_passes_on_established_discipline_keyword():
    # Reuses scraper/discipline_tags.py's vocabulary - "new media" is defined
    # there, not duplicated in relevance_allowlist.yaml.
    assert passes_strong_filter("Open call for new media art installation", organizer="Some Gallery")


def test_strong_filter_passes_on_newly_added_extra_keyword():
    assert passes_strong_filter("A residency exploring urban environment and social data", organizer="Some Org")
    assert passes_strong_filter("Creative coding workshop for artists", organizer="Some Org")


def test_strong_filter_passes_on_allowlisted_organizer_even_without_keyword_match():
    assert passes_strong_filter("Oil painting exhibition open call", organizer="Somerset House Studios")
    assert passes_strong_filter("Ceramics prize", organizer="Victoria and Albert Museum")


def test_strong_filter_blocks_irrelevant_text_and_unknown_organizer():
    assert not passes_strong_filter("Pottery workshop for beginners", organizer="Random Craft Studio")
    assert not passes_strong_filter(None, organizer=None)


def test_strong_filter_organizer_match_is_case_insensitive_substring():
    assert passes_strong_filter("Unrelated text", organizer="site gallery, sheffield")


def test_single_weak_or_format_word_does_not_pass_alone():
    # urban/research/intelligence/environmental (weak_keywords) and
    # commission/grant/fellowship/funding (format_keywords) are each worth
    # only WEAK_WEIGHT=1, below threshold=3, specifically so one generic word
    # alone can never pass - only combinations of them can.
    assert not passes_strong_filter("Business intelligence workshop for entrepreneurs", organizer="Random Corp")
    assert not passes_strong_filter("Suburban housing development plan", organizer="Random Council")
    assert not passes_strong_filter("Scientific research conference", organizer="Random University")
    assert not passes_strong_filter("Environment secretary announces new policy", organizer="Random Gov")


def test_weighted_score_lets_generic_word_combinations_pass():
    # Real case (2026-07-28) that drove the switch from a boolean filter to a
    # weighted score: "Artwork Commission - ESRC Digital Good Network...
    # artwork or visualisation representing our research and findings"
    # previously only passed via the organizer allowlist (Digital Good) - the
    # text itself matched nothing. "visualisation" is now a strong_keyword
    # (specific enough to trust alone), so this passes on text alone even
    # with an unrecognized organizer (e.g. if it had come via ArtRabbit/Art
    # Quest, neither of which captures a real per-item organizer).
    text = (
        "Artwork Commission - ESRC Digital Good Network. The network seeks an "
        "artwork or visualisation representing our research and findings."
    )
    assert relevance_score(text) >= 3
    assert passes_strong_filter(text, organizer="ArtRabbit")

    # Synthetic case: three generic words (urban/research/public engagement,
    # all weak_keywords) plus a format word (commission) with no single
    # strong_keyword present - none would pass alone, but together they clear
    # threshold=3.
    combo_text = "Urban Research Commission - public engagement project"
    assert relevance_score(combo_text) >= 3
    assert passes_strong_filter(combo_text, organizer="ArtRabbit")


def test_weighted_score_still_blocks_generic_pairs():
    # Guards against the weighted filter reopening the exact false positive
    # the original bare-word removal fixed: "curatorial research grants"
    # style text (real example: Jonathan Ruffer curatorial grants) only
    # reaches research(1) + grant(1) = 2, still below threshold=3.
    text = "Jonathan Ruffer curatorial grants - Small grants supporting curatorial research"
    assert relevance_score(text) < 3
    assert not passes_strong_filter(text, organizer="Art Fund")


def test_strong_filter_custom_config_is_user_definable(tmp_path):
    config_path = tmp_path / "relevance_allowlist.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "threshold": 2,
                "strong_keywords": ["knitting"],
                "weak_keywords": ["circle"],
                "format_keywords": ["open call"],
                "organizers": ["Acme Arts"],
            }
        ),
        encoding="utf-8",
    )

    assert passes_strong_filter("Knitting circle open call", organizer="Nobody", config_path=config_path)
    # "circle" (weak) + "open call" (format) = 2, meets this config's threshold: 2
    assert passes_strong_filter("Some circle meets for an open call", organizer="Nobody", config_path=config_path)
    # "circle" alone = 1, below threshold: 2
    assert not passes_strong_filter("A circle of friends", organizer="Nobody", config_path=config_path)
    assert passes_strong_filter("Unrelated", organizer="Acme Arts Centre", config_path=config_path)
    assert not passes_strong_filter("Unrelated", organizer="Nobody", config_path=config_path)
    # discipline_tags.py vocabulary still applies even with a custom allowlist file
    assert passes_strong_filter("New media art open call", organizer="Nobody", config_path=config_path)
