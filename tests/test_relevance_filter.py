import yaml

from scraper.relevance_filter import is_excluded, passes_strong_filter


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


def test_strong_filter_custom_config_is_user_definable(tmp_path):
    config_path = tmp_path / "relevance_allowlist.yaml"
    config_path.write_text(
        yaml.safe_dump({"extra_keywords": ["knitting"], "organizers": ["Acme Arts"]}), encoding="utf-8"
    )

    assert passes_strong_filter("Knitting circle open call", organizer="Nobody", config_path=config_path)
    assert passes_strong_filter("Unrelated", organizer="Acme Arts Centre", config_path=config_path)
    assert not passes_strong_filter("Unrelated", organizer="Nobody", config_path=config_path)
    # discipline_tags.py vocabulary still applies even with a custom allowlist file
    assert passes_strong_filter("New media art open call", organizer="Nobody", config_path=config_path)
