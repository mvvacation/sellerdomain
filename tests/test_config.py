"""Tests for configuration management."""

import yaml

from core.config import Config


class TestConfig:
    def test_default_config(self):
        cfg = Config()
        assert cfg.get("search", "engine") == "auto"
        assert cfg.get("search", "max_results_per_query") == 10
        assert cfg.get("enrichment", "scrape_websites") is True

    def test_get_nested(self):
        cfg = Config()
        assert cfg.get("cache", "ttl_hours") == 24

    def test_get_missing_returns_default(self):
        cfg = Config()
        assert cfg.get("nonexistent", "key", default="fallback") == "fallback"

    def test_load_from_file(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "search": {"engine": "ddgs", "max_results_per_query": 5},
                }
            )
        )
        cfg = Config(str(config_file))
        assert cfg.get("search", "engine") == "ddgs"
        assert cfg.get("search", "max_results_per_query") == 5
        # Other defaults preserved
        assert cfg.get("enrichment", "scrape_websites") is True

    def test_deep_merge(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "search": {"engine": "serpapi"},
                }
            )
        )
        cfg = Config(str(config_file))
        # engine overridden
        assert cfg.get("search", "engine") == "serpapi"
        # other search defaults preserved
        assert cfg.get("search", "delay_between_searches") == 2

    def test_env_override(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("SERPAPI_KEY", "test-key-123")
        cfg = Config()
        assert cfg.get("search", "serpapi_key") == "test-key-123"
        assert cfg.get("search", "engine") == "serpapi"

    def test_nonexistent_file_uses_defaults(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SERPAPI_KEY", raising=False)
        monkeypatch.chdir(tmp_path)
        cfg = Config("/nonexistent/path/config.yaml")
        assert cfg.get("search", "engine") == "auto"
