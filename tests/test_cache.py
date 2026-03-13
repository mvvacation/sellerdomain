"""Tests for file-based cache."""

import json
import time

import pytest

from core.cache import SearchCache, CACHE_DIR


@pytest.fixture(autouse=True)
def clean_cache(tmp_path, monkeypatch):
    """Use a temp directory for cache during tests."""
    test_cache_dir = tmp_path / "test_cache"
    test_cache_dir.mkdir()
    monkeypatch.setattr("core.cache.CACHE_DIR", test_cache_dir)
    yield test_cache_dir


class TestSearchCache:
    def test_set_and_get(self):
        cache = SearchCache(enabled=True, ttl_hours=24)
        cache.set("ns", "query1", {"data": "test"})
        result = cache.get("ns", "query1")
        assert result == {"data": "test"}

    def test_get_miss(self):
        cache = SearchCache(enabled=True, ttl_hours=24)
        assert cache.get("ns", "nonexistent") is None

    def test_disabled_cache_returns_none(self):
        cache = SearchCache(enabled=False)
        cache.set("ns", "q", {"data": "test"})
        assert cache.get("ns", "q") is None

    def test_ttl_expiration(self, monkeypatch):
        cache = SearchCache(enabled=True, ttl_hours=1)
        cache.set("ns", "q", {"data": "test"})

        # Verify it's there
        assert cache.get("ns", "q") is not None

        # Simulate time passing by patching the cached file
        path = cache._path("ns", "q")
        data = json.loads(path.read_text())
        data["_cached_at"] = time.time() - 7200  # 2 hours ago
        path.write_text(json.dumps(data))

        # Now it should be expired
        assert cache.get("ns", "q") is None

    def test_corrupted_cache_file(self):
        cache = SearchCache(enabled=True, ttl_hours=24)
        cache.set("ns", "q", {"data": "test"})
        path = cache._path("ns", "q")
        path.write_text("not valid json!!!")
        # Should return None and not crash
        assert cache.get("ns", "q") is None

    def test_clear(self, clean_cache):
        cache = SearchCache(enabled=True, ttl_hours=24)
        cache.set("ns", "q1", "data1")
        cache.set("ns", "q2", "data2")
        cache.clear()
        assert cache.get("ns", "q1") is None
        assert cache.get("ns", "q2") is None

    def test_stats(self):
        cache = SearchCache(enabled=True, ttl_hours=24)
        cache.set("ns", "q1", "data1")
        cache.set("ns", "q2", "data2")
        stats = cache.stats()
        assert stats["files"] == 2
        assert stats["size_bytes"] > 0

    def test_different_namespaces(self):
        cache = SearchCache(enabled=True, ttl_hours=24)
        cache.set("search", "q1", "search_data")
        cache.set("enrich", "q1", "enrich_data")
        assert cache.get("search", "q1") == "search_data"
        assert cache.get("enrich", "q1") == "enrich_data"

    def test_overwrite(self):
        cache = SearchCache(enabled=True, ttl_hours=24)
        cache.set("ns", "q", "old_data")
        cache.set("ns", "q", "new_data")
        assert cache.get("ns", "q") == "new_data"

    def test_stores_complex_data(self):
        cache = SearchCache(enabled=True, ttl_hours=24)
        data = {
            "list": [1, 2, 3],
            "nested": {"key": "value"},
            "string": "hello",
            "number": 42,
        }
        cache.set("ns", "q", data)
        assert cache.get("ns", "q") == data
