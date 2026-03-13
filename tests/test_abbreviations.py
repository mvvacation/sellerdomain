"""Tests for abbreviation expansion logic."""

import pytest

from core.abbreviations import expand_abbreviations


class TestExpandAbbreviations:
    def test_returns_required_keys(self):
        result = expand_abbreviations(["health", "track"], "healthtrack")
        assert "interpretations" in result
        assert "expanded_keywords" in result
        assert "geo_targets" in result
        assert "niche_context" in result
        assert "search_phrases" in result

    def test_geo_expansion_mv_restaurants(self):
        result = expand_abbreviations(["mv", "restaurants"], "mvrestaurants")
        # Should detect mv as Martha's Vineyard in restaurant context
        geo = result["geo_targets"]
        assert any("Martha" in g for g in geo) or any("Maldives" in g for g in geo)

    def test_industry_abbreviation_ai(self):
        result = expand_abbreviations(["ai", "tools"], "aitools")
        interps = result["interpretations"]
        assert any("artificial intelligence" in i["expansion"].lower() for i in interps)

    def test_metro_abbreviation_nyc(self):
        result = expand_abbreviations(["nyc", "food"], "nycfood")
        geo = result["geo_targets"]
        assert any("New York" in g for g in geo)

    def test_state_code_expansion(self):
        result = expand_abbreviations(["ca", "homes"], "cahomes")
        geo = result["geo_targets"]
        # Should detect California
        assert any("California" in g or "Los Angeles" in g for g in geo)

    def test_no_expansion_for_long_words(self):
        result = expand_abbreviations(["internet", "marketing"], "internetmarketing")
        # Long words shouldn't be treated as abbreviations
        interps = result["interpretations"]
        assert not any(i["token"] == "internet" for i in interps)

    def test_expanded_keywords_enriched(self):
        result = expand_abbreviations(["sf", "tech"], "sftech")
        assert len(result["expanded_keywords"]) >= 2

    def test_niche_context_built(self):
        result = expand_abbreviations(["mv", "restaurants"], "mvrestaurants")
        assert len(result["niche_context"]) > 0

    def test_search_phrases_generated(self):
        result = expand_abbreviations(["nyc", "restaurants"], "nycrestaurants")
        assert len(result["search_phrases"]) > 0

    def test_empty_input(self):
        result = expand_abbreviations([], "")
        assert result["interpretations"] == []
        assert result["geo_targets"] == []
