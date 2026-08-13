# resident-mockups

## Reference data

- `opportunity-size-chart.md` — opportunity size (annual) → revenue per week, at
  `annual / 52`. Use it whenever a conversation involves opportunity sizing or
  weekly revenue targets.

## Opportunity sizing requests

The user regularly posts raw revenue figures — usually weekly, sometimes monthly
invoices — and wants them converted into an opportunity size. Treat any bare list
of revenue numbers as this request, even without further instruction.

**Conversion**

- Weekly figures: `annual = weekly × 52`
- Monthly figures: `annual = monthly × 12`
- When averaging across periods, average first, then annualize the average —
  don't annualize each period separately and average the results.

**What to report**

1. **Lead with the most recent period**, annualized on its own. That headline
   number is the opportunity size.
2. The corresponding revenue per week (`annual / 52`).
3. The nearest row on `opportunity-size-chart.md`, naming the row's exact values.
4. Then show the blended read across all periods given, as a secondary figure.
   Call out how far apart the two are when the most recent period diverges from
   the rest, so the risk in leading with one period stays visible.

**Worked example** (3 monthly invoices, most recent first: $4,900, $3,100, $3,000)

Most recent $4,900/mo → **$58,800/yr** → **$1,130.77/wk** → nearest chart row
$60,000 ($1,153.85/wk). Blended across all three: $3,666.67/mo → $44,000/yr →
$846.15/wk — about a third lower, since the recent month runs ~60% above the
other two.
