from scraper.tier import region_tier


def test_uk_variants_are_tier_1():
    for country in ["UK", "uk", "United Kingdom", "England", "Scotland", "Wales", " GB "]:
        assert region_tier(country) == 1


def test_us_eu_taiwan_are_tier_2():
    for country in ["US", "USA", "United States", "Taiwan", "TW", "Germany", "France", "Spain"]:
        assert region_tier(country) == 2


def test_unknown_or_missing_country_is_tier_3():
    assert region_tier("Japan") == 3
    assert region_tier(None) == 3
    assert region_tier("") == 3


def test_override_always_wins():
    assert region_tier("UK", override=3) == 3
    assert region_tier(None, override=1) == 1
