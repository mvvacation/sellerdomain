"""Tests for domain analyzer — keyword extraction, industry mapping, valuation, brandability."""

from unittest.mock import patch

import pytest

from core.analyzer import DomainAnalyzer


class TestDomainAnalyzerInit:
    def test_basic_domain(self):
        a = DomainAnalyzer("example.com")
        assert a.domain == "example.com"
        assert a.name == "example"
        assert a.tld == "com"

    def test_strips_protocol(self):
        a = DomainAnalyzer("https://test.io")
        assert a.domain == "test.io"
        assert a.name == "test"
        assert a.tld == "io"

    def test_invalid_domain_raises(self):
        from core.validators import ValidationError

        with pytest.raises(ValidationError):
            DomainAnalyzer("not valid")


class TestKeywordExtraction:
    def test_single_word(self):
        a = DomainAnalyzer("cloud.com")
        a._extract_keywords()
        assert "cloud" in a.keywords

    def test_two_word_combo(self):
        a = DomainAnalyzer("healthtrack.com")
        a._extract_keywords()
        assert len(a.keywords) >= 2
        assert "health" in a.keywords

    def test_short_domain_fallback(self):
        a = DomainAnalyzer("ab.io")
        a._extract_keywords()
        assert a.keywords == ["ab"]

    def test_keywords_are_lowercase(self):
        a = DomainAnalyzer("CloudPay.com")
        a._extract_keywords()
        for kw in a.keywords:
            assert kw == kw.lower()


class TestIndustryIdentification:
    def test_tech_domain(self):
        a = DomainAnalyzer("cloudtech.com")
        a._extract_keywords()
        a._expand_abbreviations()
        a._identify_industries()
        assert "technology" in a.industries

    def test_health_domain(self):
        a = DomainAnalyzer("healthmed.com")
        a._extract_keywords()
        a._expand_abbreviations()
        a._identify_industries()
        assert "health" in a.industries

    def test_finance_domain(self):
        a = DomainAnalyzer("finpay.com")
        a._extract_keywords()
        a._expand_abbreviations()
        a._identify_industries()
        assert "finance" in a.industries

    def test_unknown_industry_gets_general(self):
        a = DomainAnalyzer("xyzqwert.com")
        a._extract_keywords()
        a._expand_abbreviations()
        a._identify_industries()
        assert "general" in a.industries

    def test_max_three_industries(self):
        a = DomainAnalyzer("healthtechfinance.com")
        a._extract_keywords()
        a._expand_abbreviations()
        a._identify_industries()
        assert len(a.industries) <= 3


class TestValuation:
    def test_value_range_positive(self):
        a = DomainAnalyzer("example.com")
        a._extract_keywords()
        a._expand_abbreviations()
        a._identify_industries()
        a._check_whois()
        a._estimate_value()
        assert a.estimated_value_low > 0
        assert a.estimated_value_high > 0
        assert a.estimated_value_low <= a.estimated_value_high

    def test_short_domain_higher_value(self):
        short = DomainAnalyzer("ab.com")
        short._extract_keywords()
        short._expand_abbreviations()
        short._identify_industries()
        short._check_whois()
        short._estimate_value()

        long = DomainAnalyzer("verylongdomainname.com")
        long._extract_keywords()
        long._expand_abbreviations()
        long._identify_industries()
        long._check_whois()
        long._estimate_value()

        assert short.estimated_value_high > long.estimated_value_high

    def test_com_higher_than_xyz(self):
        com = DomainAnalyzer("test.com")
        com._extract_keywords()
        com._expand_abbreviations()
        com._identify_industries()
        com._check_whois()
        com._estimate_value()

        xyz = DomainAnalyzer("test.xyz")
        xyz._extract_keywords()
        xyz._expand_abbreviations()
        xyz._identify_industries()
        xyz._check_whois()
        xyz._estimate_value()

        assert com.estimated_value_high > xyz.estimated_value_high


class TestBrandability:
    def test_short_domain_high_score(self):
        a = DomainAnalyzer("cloud.com")
        a._extract_keywords()
        a._expand_abbreviations()
        a._identify_industries()
        brand = a._assess_brandability()
        assert brand["score"] >= 50

    def test_brand_grade_mapping(self):
        assert DomainAnalyzer._brand_grade(85) == "A+"
        assert DomainAnalyzer._brand_grade(75) == "A"
        assert DomainAnalyzer._brand_grade(65) == "B+"
        assert DomainAnalyzer._brand_grade(55) == "B"
        assert DomainAnalyzer._brand_grade(45) == "C+"
        assert DomainAnalyzer._brand_grade(35) == "C"
        assert DomainAnalyzer._brand_grade(20) == "D"

    def test_brandability_has_factors(self):
        a = DomainAnalyzer("example.com")
        a._extract_keywords()
        a._expand_abbreviations()
        a._identify_industries()
        brand = a._assess_brandability()
        assert "factors" in brand
        assert len(brand["factors"]) > 0


class TestFullAnalysis:
    @patch("core.analyzer.whois", None)
    def test_analyze_returns_required_keys(self):
        a = DomainAnalyzer("healthtrack.com")
        result = a.analyze()
        required = [
            "domain",
            "name",
            "tld",
            "keywords",
            "industries",
            "whois",
            "dns",
            "is_registered",
            "domain_age_years",
            "estimated_value_low",
            "estimated_value_high",
            "brandability",
        ]
        for key in required:
            assert key in result, f"Missing key: {key}"

    @patch("core.analyzer.whois", None)
    def test_analyze_domain_matches(self):
        a = DomainAnalyzer("cloudpay.io")
        result = a.analyze()
        assert result["domain"] == "cloudpay.io"
        assert result["name"] == "cloudpay"
        assert result["tld"] == "io"
