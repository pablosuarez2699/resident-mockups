import json
import os
from typing import Set, Tuple
from config import CACHE_FILE, CACHE_MAX_ENTRIES
from utils.logger import get_logger

log = get_logger("cache")


class LeadCache:
    def __init__(self, path: str = CACHE_FILE):
        self._path = path
        self._seen: Set[str] = set()
        self._load()

    def _load(self) -> None:
        if os.path.exists(self._path):
            try:
                with open(self._path) as f:
                    data = json.load(f)
                self._seen = set(data.get("seen", []))
                log.info("Cache loaded: %d known leads", len(self._seen))
            except Exception as e:
                log.warning("Cache load failed (%s), starting fresh", e)
                self._seen = set()

    def _key(self, org_id: str, contact_id: str) -> str:
        return f"{org_id}::{contact_id}"

    def is_seen(self, org_id: str, contact_id: str) -> bool:
        return self._key(org_id, contact_id) in self._seen

    def mark_seen(self, org_id: str, contact_id: str) -> None:
        self._seen.add(self._key(org_id, contact_id))

    def save(self) -> None:
        entries = list(self._seen)
        if len(entries) > CACHE_MAX_ENTRIES:
            entries = entries[-CACHE_MAX_ENTRIES:]
            self._seen = set(entries)
        with open(self._path, "w") as f:
            json.dump({"seen": entries}, f)
        log.info("Cache saved: %d entries", len(entries))

    def clear(self) -> None:
        self._seen = set()
        if os.path.exists(self._path):
            os.remove(self._path)
