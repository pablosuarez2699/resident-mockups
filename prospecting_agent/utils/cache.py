import json
import os
from typing import Set
from config import CACHE_FILE, CACHE_MAX_ENTRIES
from utils.logger import get_logger

log = get_logger("cache")


class LeadCache:
    """Persistent record of every company ever returned in a report.

    Guarantees fresh batches: leads are deduped across runs by place_id AND by
    normalized company name / domain brand label, so the same business never
    reappears even if Google returns it under a new place_id or domain variant.

    The cache file is committed to git — do not delete it. `bypass=True`
    (from --no-cache) skips the seen-checks for one run but still records,
    so history is never lost.
    """

    def __init__(self, path: str = CACHE_FILE):
        self._path = path
        self._seen: Set[str] = set()
        self._names: Set[str] = set()
        self._domains: Set[str] = set()
        self.bypass = False
        self._load()

    def _load(self) -> None:
        if os.path.exists(self._path):
            try:
                with open(self._path) as f:
                    data = json.load(f)
                self._seen = set(data.get("seen", []))
                self._names = set(data.get("names", []))
                self._domains = set(data.get("domains", []))
                log.info("Cache loaded: %d ids, %d names, %d domains",
                         len(self._seen), len(self._names), len(self._domains))
            except Exception as e:
                log.warning("Cache load failed (%s), starting fresh", e)

    def _key(self, org_id: str, contact_id: str) -> str:
        return f"{org_id}::{contact_id}"

    def is_seen(self, org_id: str, contact_id: str) -> bool:
        if self.bypass:
            return False
        return self._key(org_id, contact_id) in self._seen

    def mark_seen(self, org_id: str, contact_id: str) -> None:
        self._seen.add(self._key(org_id, contact_id))

    def is_dup_name(self, norm: str) -> bool:
        """Exact or prefix match against every company ever delivered
        ('medline' matches 'medlinecanadacorporation'; min 6 chars)."""
        if self.bypass or not norm:
            return False
        if norm in self._names:
            return True
        for seen in self._names:
            shorter, longer = (norm, seen) if len(norm) <= len(seen) else (seen, norm)
            if len(shorter) >= 6 and longer.startswith(shorter):
                return True
        return False

    def is_dup_domain(self, dkey: str) -> bool:
        if self.bypass or not dkey:
            return False
        return dkey in self._domains

    def mark_company(self, norm: str, dkey: str) -> None:
        if norm:
            self._names.add(norm)
        if dkey:
            self._domains.add(dkey)

    def save(self) -> None:
        entries = list(self._seen)
        if len(entries) > CACHE_MAX_ENTRIES:
            entries = entries[-CACHE_MAX_ENTRIES:]
            self._seen = set(entries)
        with open(self._path, "w") as f:
            json.dump({
                "seen": entries,
                "names": sorted(self._names),
                "domains": sorted(self._domains),
            }, f, indent=0)
        log.info("Cache saved: %d ids, %d names, %d domains",
                 len(entries), len(self._names), len(self._domains))
