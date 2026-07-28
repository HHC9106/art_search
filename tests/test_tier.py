import pytest
import yaml

from scraper.tier import region_tier


def test_uk_variants_are_top_per_shipped_config():
    for country in ["UK", "uk", "United Kingdom", "England", "Scotland", "Wales", " GB "]:
        assert region_tier(country) == "top"


def test_us_eu_taiwan_are_high_per_shipped_config():
    for country in ["US", "USA", "United States", "Taiwan", "TW", "Germany", "France", "Spain"]:
        assert region_tier(country) == "high"


def test_unmatched_country_falls_back_to_configured_default():
    assert region_tier("Japan") == "medium"
    assert region_tier(None) == "medium"
    assert region_tier("") == "medium"


def test_override_always_wins_regardless_of_config():
    assert region_tier("UK", override="low") == "low"
    assert region_tier(None, override="top") == "top"


def test_custom_config_is_fully_user_definable(tmp_path):
    config_path = tmp_path / "tier_config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "default": "low",
                "levels": {
                    "top": ["narnia"],
                    "high": ["atlantis"],
                    "medium": ["gondor"],
                    "low": [],
                },
            }
        ),
        encoding="utf-8",
    )
    assert region_tier("Narnia", config_path=config_path) == "top"
    assert region_tier("Atlantis", config_path=config_path) == "high"
    assert region_tier("Gondor", config_path=config_path) == "medium"
    assert region_tier("Somewhere Else", config_path=config_path) == "low"


def test_invalid_default_in_config_raises(tmp_path):
    config_path = tmp_path / "tier_config.yaml"
    config_path.write_text(yaml.safe_dump({"default": "extreme", "levels": {}}), encoding="utf-8")
    with pytest.raises(ValueError):
        region_tier("anywhere", config_path=config_path)
