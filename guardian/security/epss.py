import time
import requests
import json
from pathlib import Path
from guardian.logging.logger import get_logger

log = get_logger(__name__)

class EPSSClient:
    """Client for the FIRST.org EPSS API with a file-based TTL cache."""
    def __init__(self, cache_file: Path | None = None, ttl_seconds: int = 86400):
        self.ttl = ttl_seconds
        self.endpoint = "https://api.first.org/data/v1/epss"
        
        if cache_file is None:
            from guardian.config.settings import settings
            self.cache_file = settings.project_root / ".guardian" / "epss_cache.json"
        else:
            self.cache_file = cache_file

        self._cache = self._load_cache()

    def _load_cache(self) -> dict:
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                log.warning(f"Failed to load EPSS cache: {e}")
        return {}

    def _save_cache(self) -> None:
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w") as f:
                json.dump(self._cache, f)
        except Exception as e:
            log.warning(f"Failed to save EPSS cache: {e}")

    def get_score(self, cve_id: str) -> str | None:
        """
        Fetch the EPSS score for a CVE.
        Returns the score as a string (e.g. "0.95") or "unknown" if unreachable.
        """
        now = time.time()
        
        # Check cache
        if cve_id in self._cache:
            entry = self._cache[cve_id]
            if now - entry["timestamp"] < self.ttl:
                log.debug(f"EPSS cache hit for {cve_id}")
                return entry["score"]

        # Cache miss or expired, fetch from API
        log.info(f"Fetching EPSS score for {cve_id} from API")
        try:
            resp = requests.get(f"{self.endpoint}?cve={cve_id}", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data and len(data["data"]) > 0:
                    score = data["data"][0].get("epss")
                    if score:
                        self._cache[cve_id] = {"score": score, "timestamp": now}
                        self._save_cache()
                        return score
            elif resp.status_code == 429:
                log.warning(f"EPSS API rate limit exceeded for {cve_id}")
            else:
                log.warning(f"EPSS API returned status {resp.status_code} for {cve_id}")
        except requests.RequestException as e:
            log.warning(f"EPSS API unreachable: {e}")

        # Graceful degradation
        return "unknown"

    def get_stats(self) -> dict:
        return {
            "cached_entries": len(self._cache),
            "ttl_seconds": self.ttl
        }
