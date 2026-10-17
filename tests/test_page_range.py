"""Unit tests for selective page range parsing."""

from layoutlingua.processing.page_range import parse_page_range


def test_parse_page_range_all_and_empty():
    assert parse_page_range(None, 10) == set(range(1, 11))
    assert parse_page_range("", 5) == {1, 2, 3, 4, 5}
    assert parse_page_range("all", 4) == {1, 2, 3, 4}
    assert parse_page_range("*", 3) == {1, 2, 3}


def test_parse_page_range_intervals():
    assert parse_page_range("1-3", 10) == {1, 2, 3}
    assert parse_page_range("2-4, 7, 9-10", 10) == {2, 3, 4, 7, 9, 10}
    assert parse_page_range("8-", 10) == {8, 9, 10}
    assert parse_page_range("-3", 10) == {1, 2, 3}


def test_parse_page_range_clamping_and_inverted():
    # Clamping beyond max
    assert parse_page_range("8-20", 10) == {8, 9, 10}
    # Inverted order 5-2
    assert parse_page_range("5-2", 10) == {2, 3, 4, 5}
    # Out of range single page
    assert parse_page_range("99", 5) == {1, 2, 3, 4, 5}  # fallback to all


def test_parse_page_range_standalone_and_prefixes():
    # Standalone number represents translating first N pages
    assert parse_page_range("20", 96) == set(range(1, 21))
    assert parse_page_range("5", 50) == {1, 2, 3, 4, 5}

    # Explicit page prefix targets only that page
    assert parse_page_range("p20", 96) == {20}
    assert parse_page_range("page 20", 96) == {20}
    assert parse_page_range("p.7", 10) == {7}