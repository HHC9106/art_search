from scraper.discipline_tags import auto_tag_discipline, tag_label


def test_matches_single_tag():
    assert auto_tag_discipline("Open call for new media art installations") == ["new_media_art"]


def test_matches_multiple_tags():
    tags = auto_tag_discipline("A civic tech and open data project exploring urban data")
    assert tags == ["civic_tech", "open_data", "urban_data"]


def test_case_insensitive():
    assert auto_tag_discipline("DATA ART commission") == ["data_art"]


def test_no_match_returns_empty_list():
    assert auto_tag_discipline("Open call for oil painters") == []


def test_none_or_empty_text_returns_empty_list():
    assert auto_tag_discipline(None) == []
    assert auto_tag_discipline("") == []


def test_tag_label_known_and_unknown():
    assert tag_label("civic_tech") == "Civic Tech"
    assert tag_label("not_a_real_tag") == "not_a_real_tag"
