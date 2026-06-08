import csv
import re
from typing import Dict, Optional
from utils.logger import get_logger

log = get_logger("sf_loader")


def _normalize(name: str) -> str:
    name = name.lower()
    name = re.sub(r"\b(inc|ltd|llc|corp|co|limited|incorporated)\b\.?", "", name)
    name = re.sub(r"[^a-z0-9 ]", "", name)
    return name.strip()


def load_sf_accounts(csv_path: str) -> Dict[str, dict]:
    """
    Load a Salesforce inactive accounts CSV export.

    Expected columns (case-insensitive): Account Name, Annual Revenue (or Last Billed Revenue),
    Last Activity Date (optional).

    Returns a dict keyed by normalized company name.
    """
    accounts: Dict[str, dict] = {}
    try:
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = {h.lower().strip(): h for h in (reader.fieldnames or [])}

            name_col = _find_col(headers, ["account name", "name", "company"])
            rev_col = _find_col(headers, ["annual revenue", "last billed revenue", "revenue", "billed revenue"])
            date_col = _find_col(headers, ["last activity date", "last active date", "last modified date"])

            if not name_col:
                raise ValueError("CSV must have an 'Account Name' or 'Name' column")

            for row in reader:
                raw_name = row.get(name_col, "").strip()
                if not raw_name:
                    continue
                key = _normalize(raw_name)
                accounts[key] = {
                    "original_name": raw_name,
                    "prior_year_revenue": _parse_revenue(row.get(rev_col, "") if rev_col else ""),
                    "last_active_date": row.get(date_col, "").strip() if date_col else "",
                }

        log.info("Loaded %d Salesforce accounts from %s", len(accounts), csv_path)
    except FileNotFoundError:
        log.error("Salesforce export not found: %s", csv_path)
    except Exception as e:
        log.error("Failed to load Salesforce export: %s", e)
    return accounts


def match_sf_account(company_name: str, sf_accounts: Dict[str, dict], threshold: float = 0.85) -> Optional[dict]:
    if not sf_accounts:
        return None
    key = _normalize(company_name)
    if key in sf_accounts:
        return sf_accounts[key]
    # Simple substring fuzzy match as fallback
    for sf_key, data in sf_accounts.items():
        ratio = _similarity(key, sf_key)
        if ratio >= threshold:
            return data
    return None


def _find_col(headers: dict, candidates: list) -> Optional[str]:
    for candidate in candidates:
        if candidate in headers:
            return headers[candidate]
    return None


def _parse_revenue(value: str) -> Optional[float]:
    if not value:
        return None
    cleaned = re.sub(r"[^\d.]", "", value)
    try:
        return float(cleaned)
    except ValueError:
        return None


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)
