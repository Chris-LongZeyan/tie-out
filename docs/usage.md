# Usage guide

[Back to README](../README.md)

## Command line

Run the bundled script with Python 3.10 or later:

```sh
python skills/tie-out/scripts/tie_out.py profile source.csv target.xlsx
python skills/tie-out/scripts/tie_out.py compare source.csv target.xlsx --key record_id --out reports/run-001
python skills/tie-out/scripts/tie_out.py --help
```

`profile` reports inferred types, missing values, uniqueness, and candidate keys. `compare` requires an explicit join key that identifies a record at the intended level of detail. Select a worksheet with `--source-sheet` or `--target-sheet` when an Excel workbook has multiple sheets.

## Comparison rules

| Area | Behavior |
| --- | --- |
| Input | Comma-delimited UTF-8 CSV (BOM supported), value-only XLSX, read-only SQL Server query |
| Join | Exact single or composite key, unique and nonblank on each side; text identifiers retain leading zeros |
| Numeric | Decimal comparison; absolute tolerance 0.01 by default, inclusive; per-column override with `--tolerance COLUMN=VALUE` |
| Dates | ISO dates/timestamps; zero tolerance by default; `--date-days 1` accepts up to 24 hours; per-column override with `--date-tolerance COLUMN=DAYS` |
| Strings | Exact, including case and whitespace |
| Missing values | Empty cells only; literal `NA`, `NULL`, and `NaN` remain strings |
| Schema | Shared non-key fields are compared; added or removed fields prevent a tied result |
| Invalid keys | Duplicate or blank keys cause validation to fail |
| Excel formulas | Rejected; export calculated values before comparison |
| Fuzzy | Optional `--fuzzy RATIO` suggests similar unmatched keys; the threshold must be strictly between 0 and 1 |

Types are inferred from all nonempty values on both sides. Mixed columns fall back to strings. Use repeated `--type COLUMN=numeric`, `--type COLUMN=date`, or `--type COLUMN=string` flags to make the business types explicit. Per-column numeric/date tolerances must target fields of that type; use `--type` when inference is unsuitable. Numeric-looking identifiers outside the join key should usually be forced to string.

```sh
python skills/tie-out/scripts/tie_out.py compare source.xlsx target.xlsx --source-sheet Prices --target-sheet Prices --key record_id --type price=numeric --type effective_date=date --numeric-tolerance 0.01 --date-days 0 --out reports/prices
```

Specify a composite key as a comma-separated list of column names. A per-column tolerance overrides the corresponding global tolerance for that field:

```sh
python skills/tie-out/scripts/tie_out.py compare examples/prices_source.csv examples/prices_target.csv --key record_id,effective_date --tolerance price=0.01 --out reports/composite
```

Key columns are matched exactly and are excluded from field comparisons. Do not apply a field tolerance to a column included in `--key`.

## Outputs and exit codes

Each completed comparison writes `summary.json` and a self-contained `report.html` to the output directory. Existing output files are not overwritten. Use a new directory for each run.

The JSON summary contains counts, inferred types, applied rules, schema differences, and aggregate diagnostic findings. The HTML report also contains up to 50 ranked differing cells and 50 missing keys per side. Numeric and date magnitudes have different units; their ranking is not a business materiality assessment.

Match rate is `(exact rows + rows within tolerance) / number of distinct keys across both inputs`. Source-only and target-only rows therefore reduce the match rate. When both inputs contain no rows, the match rate is undefined. Schema differences prevent a tied status.

| Exit code | Meaning |
| --- | --- |
| 0 | Comparison completed; with `--fail-on-difference`, the result is tied |
| 1 | Differences found when `--fail-on-difference` is enabled |
| 2 | Invalid input, configuration, or an operational error |

## Fuzzy proposals

Add `--fuzzy 0.85` to suggest similar unmatched keys. The threshold must be strictly between zero and one. Proposals require manual confirmation and never change the reconciliation counts. Comparisons with more than four million unmatched key pairs skip this optional analysis and explain why in the report.

## Data handling

CSV files must be comma-delimited UTF-8; a UTF-8 BOM is accepted. Formula cells in XLSX are rejected. Preserve identifiers and large decimal values as text when exporting from Excel: lost leading zeros and rounded numeric cells cannot be reconstructed.

Dates must be ISO dates/timestamps. Timezone-aware and timezone-naive timestamps cannot be compared. Tolerance checks use integer microseconds, preserving Python datetime precision without floating-point rounding. Native Excel timestamps may round to milliseconds; choose a justified date tolerance or export exact timestamps as text.

Both inputs are loaded into memory. Complete mismatch exports, automatic corrections, and three-way reconciliation are not supported.
