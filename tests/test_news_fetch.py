import pytest
from services.news_fetcher import _get_source_classification

def test_source_verification():
    assert _get_source_classification("cwc.gov.in") == "OFFICIAL"
    assert _get_source_classification("google.com") == "SECONDARY"
