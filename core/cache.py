"""Search result caching to avoid redundant lookups."""

import hashlib
import json
import os
import tempfile
import time
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
            data = json.loads(path.read_text(encoding="utf-8"))
            cached_at = data.get("_cached_at", 0)
            if time.time() - cached_at > self.ttl_hours * 3600:
                path.unlink(missing_ok=True)
                return None
            return data.get("payload")
        except (json.JSONDecodeError, OSError, KeyError):
            # Corrupted cache file — remove it
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            return None

    def set(self, namespace, query, payload):
        """Store data in cache using atomic write to prevent corruption."""
        if not self.enabled:
            return
        path = self._path(namespace, query)
        data = {"_cached_at": time.time(), "payload": payload}
        try:
            # Atomic write: write to temp file then rename
            fd, tmp_path = tempfile.mkstemp(dir=CACHE_DIR, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, default=str)
                os.replace(tmp_path, path)
            except Exception:
                # Clean up temp file on failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        except OSError:
            pass

    def clear(self):
        """Clear all cached data."""
        if CACHE_DIR.exists():
            import shutil
            shutil.rmtree(CACHE_DIR, ignore_errors=True)
            CACHE_DIR.mkdir(exist_ok=True)

    def stats(self):
        """Return cache statistics."""
        if not CACHE_DIR.exists():
            return {"files": 0, "size_bytes": 0}
        files = list(CACHE_DIR.glob("*.json"))
        total_size = sum(f.stat().st_size for f in files if f.exists())
        return {"files": len(files), "size_bytes": total_size}
