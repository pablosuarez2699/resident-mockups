# Purolator SMB Prospecting Agent

Generates a weekly Excel report of 100 qualified Canadian business leads for Purolator SMB sales reps.

## Setup

```bash
cd prospecting_agent
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
```

## Usage

```bash
# Full weekly run
python main.py --sectors retail,healthcare,tech,industrial --leads 100

# Include Salesforce reactivation matching
python main.py --sectors retail,healthcare,tech,industrial --leads 100 --sf-export ~/Downloads/sf_inactive_accounts.csv

# Single sector
python main.py --sectors industrial --leads 50

# Validate API keys only
python main.py --dry-run

# Ignore cache (re-fetch all)
python main.py --no-cache --leads 100
```

## Output

Excel file saved to `reports/purolator_leads_<SECTORS>_<DATE>.xlsx` with:
- **Sheet 1 — Leads**: scored, ranked, with hyperlinks and talking points
- **Sheet 2 — Run Summary**: sector breakdown, carrier targeting stats, top 10 by score

## API Keys Required

| Key | Where to get | Approx cost |
|-----|-------------|-------------|
| `APOLLO_API_KEY` | apollo.io → Settings → API | ~$49/month Basic |
| `ANTHROPIC_API_KEY` | console.anthropic.com | ~$0.08/run |
| `HUNTER_API_KEY` | hunter.io → API (optional) | Free tier (25/month) |

## Salesforce CSV Format

Export inactive accounts from Salesforce. The agent expects columns:
- **Account Name** (required)
- **Annual Revenue** or **Last Billed Revenue** (optional, used for 5× rule)
- **Last Activity Date** (optional)
