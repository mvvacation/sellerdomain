"""Tests for domain validation and config validation."""

import pytest

from core.validators import ValidationError, validate_config_values, validate_domain


class TestValidateDomain:
    def test_basic_domain(self):
        assert validate_domain("example.com") == "example.com"

    def test_strips_whitespace(self):
        assert validate_domain("  example.com  ") == "example.com"

    def test_lowercases(self):
        assert validate_domain("EXAMPLE.COM") == "example.com"

    def test_strips_protocol_https(self):
        assert validate_domain("https://example.com") == "example.com"

    def test_strips_protocol_http(self):
        assert validate_domain("http://example.com") == "example.com"

    def test_strips_www(self):
        assert validate_domain("www.example.com") == "example.com"

    def test_strips_path(self):
        assert validate_domain("example.com/path/to/page") == "example.com"

    def test_strips_full_url(self):
        assert validate_domain("https://www.example.com/page") == "example.com"

    def test_subdomain(self):
        assert validate_domain("sub.example.com") == "sub.example.com"

    def test_io_tld(self):
        assert validate_domain("test.io") == "test.io"

    def test_ai_tld(self):
        assert validate_domain("myapp.ai") == "myapp.ai"

    def test_co_uk_tld(self):
        assert validate_domain("example.co.uk") == "example.co.uk"

    def test_empty_string_raises(self):
        with pytest.raises(ValidationError, match="non-empty"):
            validate_domain("")

    def test_none_raises(self):
        with pytest.raises(ValidationError, match="non-empty"):
            validate_domain(None)

    def test_invalid_format_raises(self):
        with pytest.raises(ValidationError, match="Invalid domain"):
            validate_domain("not a domain")

    def test_no_tld_raises(self):
        with pytest.raises(ValidationError, match="Invalid domain"):
            validate_domain("justtext")

    def test_special_characters_raises(self):
        with pytest.raises(ValidationError, match="Invalid domain"):
            validate_domain("exam ple.com")

    def test_too_long_raises(self):
        long = "a" * 250 + ".com"
        with pytest.raises(ValidationError, match="maximum length"):
            validate_domain(long)

    def test_hyphenated_domain(self):
        assert validate_domain("my-domain.com") == "my-domain.com"


class TestValidateConfigValues:
    def test_valid_config_no_warnings(self):
        config = {
            "search": {"max_results_per_query": 10, "delay_between_searches": 2},
            "enrichment": {"request_timeout": 10, "max_enrich": 20},
            "leads": {"min_score": 20},
        }
        warnings = validate_config_values(config)
        assert warnings == []

    def test_warns_high_results(self):
        config = {"search": {"max_results_per_query": 100}}
        warnings = validate_config_values(config)
        assert any("rate limiting" in w for w in warnings)

    def test_warns_low_delay(self):
        config = {"search": {"delay_between_searches": 0.5}}
        warnings = validate_config_values(config)
        assert any("rate limiting" in w for w in warnings)

    def test_warns_low_timeout(self):
        config = {"enrichment": {"request_timeout": 1}}
        warnings = validate_config_values(config)
        assert any("timeout" in w.lower() for w in warnings)

    def test_warns_high_enrich(self):
        config = {"enrichment": {"max_enrich": 100}}
        warnings = validate_config_values(config)
        assert any("slow" in w for w in warnings)

    def test_warns_high_min_score(self):
        config = {"leads": {"min_score": 90}}
        warnings = validate_config_values(config)
        assert any("filter" in w for w in warnings)

    def test_empty_config_no_warnings(self):
        assert validate_config_values({}) == []
