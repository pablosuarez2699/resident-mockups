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

- Weekly figures: `annual = average weekly × 52`
- Monthly figures: `annual = average monthly × 12`
- Always average across all periods given, then annualize the average — don't
  annualize each period separately and average the results.

**What to report**

1. The annual opportunity size.
2. The corresponding revenue per week (`annual / 52`).
3. The nearest row on `opportunity-size-chart.md`, naming the row's exact values.
4. If the periods vary widely, flag it and show the alternative reads side by
   side — the most recent period as a new baseline vs. treating the outlier as a
   one-off — because the blend can hide a materially different answer. Recommend
   the blended figure as the defensible number unless the user says what changed.

**Worked example** (3 monthly invoices: $4,900, $3,100, $3,000)

Average $3,666.67/mo → **$44,000/yr** → **$846.15/wk** → nearest chart row
$45,000 ($865.38/wk). The $4,900 month runs ~60% above the others, so the
alternative reads were $58,800/yr (new baseline) and $36,600/yr (spike).
