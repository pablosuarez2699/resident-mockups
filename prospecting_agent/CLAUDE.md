# CLAUDE.md — Purolator SMB Prospecting Agent

Project memory for Claude Code. Read this before working in `prospecting_agent/`.
If you build a *new* agent that should resemble this one, mirror the conventions below.

## What this is

A CLI tool that generates a weekly Excel report of ~100 qualified Canadian B2B
business leads for Purolator SMB sales reps. It discovers companies, finds
decision-makers + contact info, scores shipping potential (1–10) with Claude,
and writes a formatted `.xlsx`.

Run it: `python main.py --sectors all --leads 100 --randomize`

## Core design philosophy

1. **Free-first, paid-optional.** The default path uses zero-recurring-cost APIs
   (Google Places within its $200/mo free credit, Hunter free tier, web
   scraping, Claude at ~$0.08/run). A paid premium path (Apollo.io) is fully
   preserved and switchable. **When adding a data source, always ask: is there
   a free equivalent? Default to it; keep the paid one behind a toggle.**
2. **Provider-agnostic pipeline.** Everything downstream of fetching
   (qualification, scoring, Excel output, Salesforce matching, LinkedIn URLs)
   operates on the `Lead` dataclass and knows nothing about where leads came
   from. New sources only touch `fetcher.py` + a new `clients/` module.
3. **Single-env-var toggles.** Behavior switches live in `.env` and are read in
   `config.py` only. `LEAD_SOURCE=google|apollo`, `APOLLO_PLAN=free|paid`.

## Architecture & data flow

```
main.py (click CLI)
  → agent.run()  — orchestrator, rich progress, error recovery
      → pipeline/fetcher.fetch_sector()   — dispatches on LEAD_SOURCE/APOLLO_PLAN
          → clients/google_places_client | apollo_client | osm_client
          → pipeline/web_scraper (contact fallback)
          → clients/hunter_client.domain_search (contact enrichment)
      → pipeline/qualifier.rule_qualify_all()   — fast, free pre-score
      → pipeline/linkedin_builder.build_urls_batch()
      → utils/sf_loader + match_sf_account()     — REACTIVATION tagging
      → clients/claude_client.qualify_leads_batch()  — Claude refines score
      → output/excel_writer.write_excel()
```

## Directory conventions

| Dir | Role | Rule |
|-----|------|------|
| `clients/` | One module per external API. Stateless functions, not classes. | Each gets its own `RateLimiter` instance + `get_logger("<name>")`. Wrap calls in try/except, log + return empty/None on failure — never crash the pipeline. |
| `pipeline/` | Transformation stages operating on `List[Lead]`. | Pure-ish; take leads in, return leads out. |
| `models/` | `lead.py` (the `Lead` dataclass — the universal currency) + `sector_config.py`. | Add fields to `Lead` rather than passing side dicts. |
| `output/` | Formatters (currently Excel). | |
| `utils/` | `rate_limiter`, `logger`, `cache`, `sf_loader`. | Reuse these; don't reinvent. |
| `prompts/` | `.txt` files loaded at runtime, `.format()`-templated. | Keep prompts out of code. |

## Key conventions to follow

- **Config:** all env vars + constants live in `config.py`. Read via
  `config.X`. Provide a default in `os.getenv(...)`. Never call `os.getenv`
  outside `config.py`.
- **Rate limiting:** every external client instantiates a module-level
  `_limiter = RateLimiter(spacing_seconds)` and calls `_limiter.wait()` before
  each request. Spacing constants go in `config.py`.
- **Retries:** use `tenacity` `@retry` with exponential backoff on
  `requests.RequestException` (see `hunter_client._get` for the pattern).
- **Logging:** `from utils.logger import get_logger; log = get_logger("name")`.
  Use lazy `%s` formatting, not f-strings, in log calls.
- **Failure handling:** clients log a warning/error and return a safe empty
  value (`[]`, `{}`, `None`, `("", 0)`). The run continues with partial data.
- **Claude calls:** use prompt caching — system prompt as a `system=[{type,
  text, cache_control:{type:"ephemeral"}}]` block. Model is
  `config.CLAUDE_MODEL` (default `claude-sonnet-4-6`). Parse JSON defensively
  (strip ``` fences, fall back to rule_score on parse failure).
- **Caching / FRESHNESS GUARANTEE (user directive — do not violate):** every
  batch must contain only never-before-delivered companies. `utils/cache.LeadCache`
  enforces this persistently three ways: place_id (`is_seen`), normalized company
  name with prefix matching (`is_dup_name` — "Medline" == "Medline Canada Corp"),
  and domain brand label (`is_dup_domain` — medline.ca == medline.com).
  `.lead_cache.json` is **committed to git** so history survives ephemeral
  containers — NEVER delete it, never re-gitignore it, and commit it after every
  run. `--no-cache` only bypasses checks for one run (testing); it must never
  delete history. If the lead well runs dry, expand `google_search_terms` with
  city-specific variants instead of clearing the cache.

## Lead source paths (current state)

- **`LEAD_SOURCE=google`** (default): Google Places Text Search → B2B type
  filter (`_is_b2b_place`) → Hunter `domain_search` (budget-limited by
  `HUNTER_DOMAIN_SEARCH_BUDGET`) → web scraper fallback. OSM Overpass is the
  no-key fallback when Google key is absent.
- **`LEAD_SOURCE=apollo`**: original path. `APOLLO_PLAN=free` = org-search only
  (lookup-assist, no contacts); `APOLLO_PLAN=paid` = people-search with emails.

Per-sector search config lives in `models/sector_config.py`:
`apollo_keywords`/`apollo_industries` (Apollo path) and `google_search_terms`
(B2B-specific, Google path). Sectors: `retail`, `healthcare`, `tech`,
`industrial`. `--sectors all` expands to all four.

## Business rules (domain logic — preserve these)

- **B2B *and* B2C, gated by shipping volume:** the only structural filter is
  `_NEVER_SHIPS_TYPES` in `fetcher.py` (`_is_shipping_capable_place`), which drops
  local-service types that never ship parcels (restaurant, salon, gym, hotel,
  dentist, auto shop, etc.). Retail/store types are deliberately **allowed** —
  a B2C e-commerce / DTC brand qualifies if it ships as much as a B2B (5+
  parcels/day). The real gate is the `MIN_DAILY_SHIPMENTS` spend filter +
  Claude's per-company volume estimate, NOT the customer type. Search terms
  cover both B2B (distributor, supplier, manufacturer, wholesaler) and B2C
  high-volume shippers (DTC brand, online retailer, subscription box).
- **3PL risk:** companies on a *group/3PL discount account* get
  `shipping_score` capped at 4 (`three_pl_risk`). Companies with their *own*
  ShipStation/Shippo account are still winnable — NOT flagged.
- **Reactivation:** Salesforce CSV (`--sf-export`) matches old accounts → tagged
  `REACTIVATION`, subject to a 5× prior-revenue viability check by Claude.
- **Carrier targeting:** Claude estimates FedEx/UPS incumbency →
  `current_carrier_estimated`, used for competitive talking points.

## Cost guardrails

Free path total ≈ $0.32/month. If you add a source, document its cost in the
README cost table and keep the free path genuinely free. Google Places stays
free only because volume is ~80 calls/run; don't add per-lead Place Details
calls casually.

## Gotchas

- `pip install pkg>=x.y` in this shell creates literal `=x.y` files — quote it:
  `pip install "pkg>=x.y"`.
- The environment is ephemeral; **commit + push** anything to keep it. Dev
  branch for this work: see the active session's branch instructions.
- `diagnose_apollo.py` / `diagnose_top_people.py` are throwaway debug scripts,
  not part of the pipeline.
- Never print/commit API key values. `.env` is gitignored; `.env.example` is the
  template.
