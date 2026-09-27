# From differences to checks

The script reports observations. These hypotheses guide the next investigation, not automatic corrections.

| Evidence | Possible explanation | Next check |
| --- | --- | --- |
| Repeated numeric offset | Systematic adjustment, rounding rule, transformation | Compare calculation order, precision, and fee treatment |
| Repeated date delta | Effective-date lag or timestamp convention | Compare effective dates, UTC offsets, and batch cutoffs |
| Source-only or target-only keys | Coverage gap, filter difference, changed identifiers | Compare extraction windows and identifier construction |
| Null mismatches | Incomplete enrichment or different missing-value conventions | Inspect upstream null handling; literal `NA` is a string here |
| String differences | Case, whitespace, mapping, or real label changes | Check normalization rules before proposing a rerun |
| Duplicate keys (comparison stopped) | Wrong key, repeated exports, or join fan-out | Establish row grain and inspect upstream joins |
| Fuzzy proposals above threshold | Key typos or identifier variants; unconfirmed | Confirm each pair manually; never count proposals as matches |

Do not infer unit scaling from a constant offset: scaling requires ratio evidence. Do not claim a period-boundary cluster or feed outage from missing-row counts alone. The v1 summary does not measure those distributions. Request a focused, local aggregate analysis if the user needs stronger evidence. Do not inspect raw rows in model context to fill the gap.

Summarize the outcome in this order: coverage, matching rows, field discrepancies, supported hypotheses, one or two concrete next checks, report link. Mention if all rows pass only because nonzero tolerances were allowed. Schema-only differences still prevent a clean tie-out.
