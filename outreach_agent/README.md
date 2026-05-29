# Purolator SMB Outreach Agent

The next step after the [Purolator SMB Prospecting Agent](../prospecting_agent/).
Where the prospecting agent *finds* qualified Canadian B2B leads and writes a
`.xlsx`, this agent *ingests* that spreadsheet (or any Excel/CSV of accounts +
decision-maker contacts) and **composes personalized, consultative outreach
emails** — one tailored email per lead, in batch.

It's built for a **phone-first** workflow. You call first; the email is the
follow-up. Two modes, selected by a trigger keyword when you run it:

- **`--mode no-answer`** — you tried them by phone and couldn't connect. A brief,
  courteous introduction + your contact info, no pressure.
- **`--mode follow-up`** — you spoke with them. A thank-you, a recap of what you
  discussed, a clear next step/proposal, and your contact info.

Every email is written as a **solutions consultant, not a salesperson**, and is
**relationship-aware** — most SMBs already ship (or used to ship) with Purolator,
so the copy leans on that existing relationship to position you strategically.

## Setup

```bash
cd outreach_agent
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set REP_NAME / REP_TITLE / REP_PHONE / REP_EMAIL,
# and ANTHROPIC_API_KEY for the best (Claude) composition.
```

## Usage

```bash
# Intro emails for everyone you couldn't reach by phone (Claude, default)
python main.py --mode no-answer --input data/sample_leads.csv

# Post-call follow-ups with proposal + contact info
python main.py --mode follow-up --input data/sample_leads.csv

# Reading the prospecting agent's Excel report directly
python main.py --mode no-answer --input ../prospecting_agent/reports/purolator_leads_*.xlsx --source excel

# Free, zero-cost template path (no API key needed)
COMPOSE_MODE=template python main.py --mode no-answer --input data/sample_leads.csv

# Validate parsing + config without composing or writing
python main.py --mode follow-up --input data/sample_leads.csv --dry-run

# One-off, single contact (no file)
python main.py --mode follow-up --source manual \
  --company "Maple Ridge Distributors" --name "Sarah Chen" \
  --email schen@mapleridgedist.ca --relationship current \
  --carrier FedEx --call-notes "Wants a Q3 rate review; transit times to the Prairies."
```

Mode triggers accept aliases: `no-answer` (also `intro`, `missed`, `voicemail`,
`vm`) and `follow-up` (also `post-call`, `proposal`, `recap`).

## Composition modes (free-first, paid-optional)

| `COMPOSE_MODE` | What happens | Cost |
|----------------|--------------|------|
| `llm` (default) | Claude writes each email, tailored to the lead's industry, relationship, carrier, and your call notes. | ~pennies/run |
| `template` | Deterministic relationship-aware templates filled with the lead's fields. | Free |

If `COMPOSE_MODE=llm` but no `ANTHROPIC_API_KEY` is set, the agent automatically
uses the free template path. If a single Claude call fails, that lead falls back
to the template — the batch never crashes.

## Input columns

Headers are matched case/space-insensitively, so the prospecting agent's report
works as-is. Recognized columns include: `Company Name`, `Decision Maker` (or
`Contact` / `First Name` + `Last Name`), `Title`, `Email`, `Phone`, `City`,
`Province`, `Industry`, `Carrier (Est.)`, `Talking Points`, `Lead Type`,
`Relationship`, `Call Notes`, `Account Notes`. Only `Company Name` (or a contact
name) is required; rows missing an email still get a draft, flagged for
phone-only use.

`Relationship` should be one of `current | lapsed | past | prospect`. If absent,
it's inferred from `Lead Type` (`REACTIVATION` → lapsed, `NEW` → prospect).

## Output

Written to `drafts/` (gitignored):

- One Markdown file per lead — `NN_<Company>_<Name>.md` — with To / Subject /
  body, ready to copy into your mail client.
- A Purolator-styled `.xlsx` tracking index —
  `purolator_outreach_<MODE>_<DATE>.xlsx` — listing every draft, subject, and
  status so you can work the batch.

## Scaling to many leads

The shipped run is sequential and rate-limited (safe and simple). For very large
batches, the work fans out cleanly to Claude-Code-level parallel subagents — see
`CLAUDE.md`.
