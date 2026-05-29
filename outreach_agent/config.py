import os
from dotenv import load_dotenv

load_dotenv()


def require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(f"Missing required env var: {key}")
    return val


# ── Anthropic (Claude email composition) ─────────────────────────────────────
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

# "llm"      → Claude composes each email (best tailoring; needs ANTHROPIC_API_KEY)
# "template" → deterministic .format() templates only (free, zero-cost fallback)
# The llm path automatically falls back to the template path when no key is set.
COMPOSE_MODE: str = os.getenv("COMPOSE_MODE", "llm")

# "excel"  → read a .xlsx of leads (default; the format the prospecting agent emits)
# "csv"    → read a .csv of leads
# "manual" → build a single lead from CLI flags (no input file)
LEAD_SOURCE: str = os.getenv("LEAD_SOURCE", "excel")
INPUT_FILE: str = os.getenv("INPUT_FILE", "")

# ── Rep identity (used in every signature / contact block) ───────────────────
REP_NAME: str = os.getenv("REP_NAME", "Your Name")
REP_TITLE: str = os.getenv("REP_TITLE", "Account Executive, Purolator")
REP_PHONE: str = os.getenv("REP_PHONE", "(000) 000-0000")
REP_EMAIL: str = os.getenv("REP_EMAIL", "you@purolator.com")
REP_BOOKING_LINK: str = os.getenv("REP_BOOKING_LINK", "")

# ── Paths ─────────────────────────────────────────────────────────────────────
OUTPUT_DIR: str = os.path.join(os.path.dirname(__file__), os.getenv("OUTPUT_DIR", "drafts"))
CACHE_FILE: str = os.path.join(os.path.dirname(__file__), ".outreach_cache.json")

# ── Rate limiting ─────────────────────────────────────────────────────────────
ANTHROPIC_MIN_SPACING_S: float = float(os.getenv("ANTHROPIC_MIN_SPACING_S", "0.5"))
