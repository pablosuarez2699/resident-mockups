# Purolator SMB Prospecting Agent

Generates a weekly Excel report of 100 qualified Canadian B2B business leads for Purolator SMB sales reps. Surfaces decision-makers (Purchasing Manager, VP Operations, COO, etc.) with contact info, shipping score, carrier signals, and personalized talking points.

## Setup

```bash
cd prospecting_agent
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys (see below)
```

## Usage

```bash
# All sectors, free Google path (default)
python main.py --sectors all --leads 100

# Randomized mix across sectors (shuffled within score bands)
python main.py --sectors all --leads 100 --randomize

# Single sector deep-dive
python main.py --sectors industrial --leads 50

# Any combination of sectors
python main.py --sectors retail,healthcare --leads 60

# Include Salesforce reactivation matching
python main.py --sectors all --leads 100 --sf-export ~/Downloads/sf_inactive_accounts.csv

# Validate API keys without generating leads
python main.py --dry-run

# Force re-fetch (ignore cache)
python main.py --sectors all --no-cache --leads 100

# Use Apollo instead (personal use / when subscribed)
LEAD_SOURCE=apollo python main.py --sectors all --leads 100
```

## Lead Sources

### Free path (default — `LEAD_SOURCE=google`)

| Stage | Source | Cost |
|-------|--------|------|
| Company discovery | Google Places API (New) | ~$2/run — under $200/mo free credit, **always free** |
| Company fallback | OpenStreetMap Overpass API | Free, no key |
| Contact enrichment | Hunter.io domain-search | 25 lookups/mo free tier |
| Contact fallback | Website scraper (`/team`, `/about`, `/contact`) | Free |
| Lead qualification | Claude API | ~$0.08/run |
| **Total** | | **~$0.32/month** |

### Apollo path (`LEAD_SOURCE=apollo`)

| Key | Where to get | Cost |
|-----|-------------|------|
| `APOLLO_API_KEY` | apollo.io → Settings → API | ~$49/month Basic |
| `HUNTER_API_KEY` | hunter.io → API | ~$34/month Starter |
| `ANTHROPIC_API_KEY` | console.anthropic.com | ~$0.08/run |
| **Total** | | **~$83/month** |

## API Keys (`.env`)

```bash
# Required for free path
LEAD_SOURCE=google
GOOGLE_PLACES_API_KEY=...   # console.cloud.google.com → enable "Places API (New)"
ANTHROPIC_API_KEY=...       # console.anthropic.com

# Optional — improves contact enrichment on free path
HUNTER_API_KEY=...
HUNTER_DOMAIN_SEARCH_BUDGET=25   # 25 = free tier; 500 = $34/mo paid tier

# Apollo path (set LEAD_SOURCE=apollo to use)
APOLLO_API_KEY=...
APOLLO_PLAN=free
```

## Output

Excel file saved to `reports/purolator_leads_<SECTORS>_<DATE>.xlsx`:

- **Sheet 1 — Leads**: company, decision-maker, contact info, shipping score (1–10), carrier signal, 3PL risk flag, talking points, Sales Navigator link
- **Sheet 2 — Run Summary**: sector breakdown, top 10 by score, API usage

## Salesforce Reactivation Matching

Pass a Salesforce inactive-accounts CSV export with `--sf-export`. The agent cross-references fetched companies against old Purolator accounts and flags matches as `REACTIVATION` with a 5× revenue rule check.

Expected CSV columns: `Account Name` (required), `Annual Revenue` or `Last Billed Revenue` (optional), `Last Activity Date` (optional).
