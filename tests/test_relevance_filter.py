import yaml

from scraper.relevance_filter import is_excluded


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
