"""Search result caching to avoid redundant lookups."""

import hashlib
import json
import os
from pathlib import Path


CACHE_DIR = Path(".domainseller_cache")


class SearchCache:
    """File-based cache for search results and enrichment data."""

    def __init__(self, enabled=True, ttl_hours=24):
        self.enabled = enabled
        self.ttl_hours = ttl_hours
        if enabled:
            CACHE_DIR.mkdir(exist_ok=True)

    def _key(self, namespace, query):
        raw = f"{namespace}:{query}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _path(self, namespace, query):
        return CACHE_DIR / f"{namespace}_{self._key(namespace, query)}.json"

    def get(self, namespace, query):
        """Retrieve cached data. Returns None if miss or expired."""
        if not self.enabled:
            return None
        path = self._path(namespace, query)
        if not path.exists():
            return None
        try:
            import time
            data = json.loads(path.read_text(encoding="utf-8"))
            cached_at = data.get("_cached_at", 0)
            if time.time() - cached_at > self.ttl_hours * 3600:
                path.unlink(missing_ok=True)
                return None
            return data.get("payload")
        except Exception:
            return None

    def set(self, namespace, query, payload):
        """Store data in cache."""
        if not self.enabled:
            return
        import time
        path = self._path(namespace, query)
        data = {"_cached_at": time.time(), "payload": payload}
        path.write_text(json.dumps(data, default=str), encoding="utf-8")

    def clear(self):
        """Clear all cached data."""
        if CACHE_DIR.exists():
            import shutil
            shutil.rmtree(CACHE_DIR)
            CACHE_DIR.mkdir(exist_ok=True)
