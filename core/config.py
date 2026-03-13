"""Configuration management for Domain Seller."""

import os
from pathlib import Path

import yaml


DEFAULT_CONFIG = {
    "search": {
        "engine": "auto",
        "serpapi_key": "",
        "max_results_per_query": 10,
        "delay_between_searches": 2,
    },
    "enrichment": {
        "scrape_websites": True,
        "request_timeout": 10,
        "max_enrich": 20,
    },
    "leads": {
        "max_leads": 20,
        "min_score": 20,
    },
    "output": {
        "verbose": False,
        "auto_export": "",
    },
    "cache": {
        "enabled": True,
        "ttl_hours": 24,
    },
}


class Config:
    """Application configuration loaded from YAML file and environment variables."""

    def __init__(self, config_path=None):
        self.data = dict(DEFAULT_CONFIG)
        if config_path and Path(config_path).exists():
            self._load_file(config_path)
        elif Path("config.yaml").exists():
            self._load_file("config.yaml")
        self._load_env_overrides()

    def _load_file(self, path):
        with open(path, "r", encoding="utf-8") as f:
            file_data = yaml.safe_load(f) or {}
        self._deep_merge(self.data, file_data)

    def _deep_merge(self, base, override):
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def _load_env_overrides(self):
        """Override config with environment variables."""
        env_key = os.environ.get("SERPAPI_KEY", "")
        if env_key:
            self.data["search"]["serpapi_key"] = env_key
            self.data["search"]["engine"] = "serpapi"

    def get(self, *keys, default=None):
        """Get a nested config value. Usage: config.get('search', 'engine')"""
        current = self.data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current
