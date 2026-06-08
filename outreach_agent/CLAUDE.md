# CLAUDE.md — Purolator SMB Outreach Agent

Project memory for Claude Code. Read this before working in `outreach_agent/`.
This agent is the **continuation of** `../prospecting_agent/` and deliberately
mirrors its conventions (see `../prospecting_agent/CLAUDE.md`). When in doubt,
match the sibling.

## What this is

A CLI tool that turns a spreadsheet of leads/accounts + decision-maker contacts
into **personalized, consultative outreach emails** — one tailored email per
lead, in batch. The prospecting agent *produces* the qualified-leads `.xlsx`;
this agent *consumes* it (or any Excel/CSV) and *writes the emails*.

Phone-first workflow. The email always follows a call attempt, in one of two
modes selected by a trigger keyword:

```
python main.py --mode no-answer  --input data/sample_leads.csv   # couldn't reach by phone → intro
python main.py --mode follow-up  --input data/sample_leads.csv   # spoke with them → recap + proposal
```

## Core design philosophy

1. **Free-first, paid-optional.** `COMPOSE_MODE=llm` (default) uses Claude for
   genuinely tailored emails; `COMPOSE_MODE=template` is a zero-cost
   deterministic path. The llm path auto-falls back to templates when no
   `ANTHROPIC_API_KEY` is present, and a failed Claude call falls back per-lead.
   **When adding any external call, keep a free equivalent and default to it.**
2. **Consultative, not salesy — and relationship-aware.** Every email is written
   as a solutions consultant. Most SMBs already ship (or used to) with Purolator;
   the copy uses that relationship (`current | lapsed | past | prospect`) as
   strategic positioning, never as a hard sell. This rule lives in
   `prompts/system_prompt.txt` and the `_RELATIONSHIP` snippets in
   `pipeline/composer.py`.
3. **Provider-agnostic pipeline.** Everything downstream of ingest operates on
   the `Lead` dataclass and is agnostic to where leads came from. A new input
   format only touches `pipeline/ingester.py`.
4. **Single-env-var toggles.** Behavior switches live in `.env`, read in
   `config.py` only: `COMPOSE_MODE=llm|template`, `LEAD_SOURCE=excel|csv|manual`.

## Architecture & data flow

```
main.py (click CLI; --mode trigger lives here)
  → models/mode_config.resolve_mode(keyword)   — keyword/alias → OutreachMode
  → agent.run(mode, input_path | manual_lead, dry_run)
      → pipeline/ingester.ingest(path)          — dispatch on LEAD_SOURCE → List[Lead]
      → pipeline/composer.compose_all(leads, mode)   — rich progress; per-lead EmailDraft
          → build_fields(lead)                  — shared .format() fields + relationship/carrier snippets
          → COMPOSE_MODE=llm + key → clients/claude_client.compose_email(...)
          → else / on failure      → render_template(...) using templates/<mode>.txt
      → output/draft_writer.write_drafts(drafts, mode)   — per-lead .md + Purolator .xlsx index
```

## Directory conventions (mirrors the prospecting agent)

| Dir | Role | Rule |
|-----|------|------|
| `clients/` | One module per external API (currently just Claude). Stateless functions. | Owns its own `RateLimiter` + `get_logger`. Wrap calls in try/except; log + return `None`/empty on failure — never crash the batch. |
| `pipeline/` | Stages operating on `List[Lead]` → `List[EmailDraft]`. | `ingester` (in) and `composer` (transform). |
| `models/` | `lead.py` (universal currency, superset-compatible with the prospecting `Lead`), `email_draft.py`, `mode_config.py`. | Add fields to `Lead` rather than passing side dicts. |
| `output/` | Writers (`.md` per lead + `.xlsx` index). | Reuse the prospecting purple branding. |
| `prompts/` | `.txt` files loaded at runtime, `.format()`-templated. | Keep prompts out of code. `system_prompt.txt` is cached. |
| `templates/` | Deterministic free-path email bodies, `.format()`-templated. | One per mode; snippets are precomputed in `composer.build_fields`. |
| `utils/` | `rate_limiter`, `logger` — verbatim copies from the prospecting agent. | Reuse; don't reinvent. |

## Key conventions to follow

- **Config:** all env vars + constants in `config.py`; read via `config.X`.
  Never call `os.getenv` elsewhere. CLI flags in `main.py` may override
  `config.LEAD_SOURCE` / `config.COMPOSE_MODE` before other modules import it.
- **Logging:** `from utils.logger import get_logger; log = get_logger("name")`.
  Lazy `%s` formatting, not f-strings, in log calls.
- **Rate limiting:** the Claude client holds a module-level
  `_limiter = RateLimiter(config.ANTHROPIC_MIN_SPACING_S)` and calls
  `_limiter.wait()` before each request.
- **Claude calls:** prompt caching — system prompt as a `system=[{type, text,
  cache_control:{type:"ephemeral"}}]` block. Model is `config.CLAUDE_MODEL`
  (default `claude-sonnet-4-6`). Parse JSON defensively (strip ``` fences),
  return `None` on any failure so the composer falls back to the template.
- **Failure handling:** ingester/clients log a warning/error and return a safe
  value (`[]`, `None`); the run continues with partial data.
- **The two modes** are data, not code: defined in `models/mode_config.py`
  (`OUTREACH_MODES` + `resolve_mode`). Add a mode by adding an entry there plus a
  `prompts/compose_<x>.txt` and a `templates/<x>.txt` — nothing else changes.

## Email voice & positioning (domain logic — preserve)

- Solutions consultant, not salesperson. 90–160 words. One low-friction ask.
- Relationship-aware (`relationship_status`): reinforce (current), warmly
  reconnect (lapsed/past), or introduce (prospect). Never guilt-trip.
- Phone-first framing per mode: "tried to reach you" (no_answer) vs "thanks for
  speaking with me" (follow_up). Always close with the rep's signature
  (`REP_*` in `config.py`).
- Competitive angle only when natural and only when the estimated carrier is
  FedEx/UPS — one understated line on Canadian network depth + bilingual support.
- Never invent prices, commitments, or facts.

## Scaling with subagents

The shipped run is **sequential + rate-limited** (mirrors the prospecting agent's
`qualify_leads_batch`) — simple and safe. For very large lead lists, fan out at
the **Claude-Code level**: split the input spreadsheet into N chunks and launch N
parallel `Agent` subagents, each running this CLI on its chunk into the same
`drafts/` dir, then collate the `.xlsx` indexes. Keep code-level concurrency out
of the script unless rate limits are explicitly raised.

## Gotchas

- `pip install pkg>=x.y` in this shell creates literal `=x.y` files — quote it:
  `pip install "pkg>=x.y"`.
- The environment is ephemeral; **commit + push** anything to keep it. Dev branch
  for this work: see the active session's branch instructions.
- `drafts/*.md` and `drafts/*.xlsx` are gitignored (they're generated + may
  contain contact data). `.env` is gitignored; `.env.example` is the template.
- Never print/commit API key values.
