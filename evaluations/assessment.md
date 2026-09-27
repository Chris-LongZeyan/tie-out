# Benchmark methodology and results

This assessment records the file-comparison benchmarks and their limitations. The initial study on 2026-09-16 compared baseline `7eb451b` with optimized implementation `5e52c7e`; SQL Server was outside its scope. Later measurements are reported separately because the implementations and environments differ.

| Measurement date | Implementation | Result record |
| --- | --- | --- |
| 2026-09-16 | `7eb451b` and `5e52c7e` | [Baseline](results/2026-09-16/baseline.json), [optimized](results/2026-09-16/optimized.json), and [DataComPy](results/2026-09-16/datacompy.json) |
| 2026-09-22 | `b3398e5` | Reported measurements; raw run files unavailable |
| 2026-09-24 | `b3398e5` | [Reproduced benchmark](results/2026-09-24/benchmark.json) |
| 2026-09-27 | `0a94099` and the current optimization | [Previous](results/2026-09-27/before.json), [current](results/2026-09-27/current.json), [DataComPy](results/2026-09-27/datacompy.json), and [validation](results/2026-09-27/validation.json) |

## Current benchmark: 2026-09-27

The current runtime avoids redundant CSV conversion, caches up to 4,096 distinct values during each column's type inference, builds each key index once, aggregates already-validated identical rows, and selects the smallest 50 missing keys without sorting every missing key. Explicit numeric/date type overrides still validate every cell, including equal values. The inference cache is bounded and local to one column scan.

The benchmark uses the six-column synthetic fixtures and expected counts described below. Previous runtime, current runtime, and DataComPy were measured sequentially in the same Python 3.13.7 environment on Windows 11 with 16 logical CPUs and 31.4 GiB RAM. Each result is the median of three fresh processes, including startup, loading, comparison, and report generation. Memory is the maximum Windows peak working set. Source hashes use UTF-8 text with LF line endings and identify the exact engines in the raw records.

| CSV rows per file | Previous seconds / MiB | Current seconds / MiB | DataComPy seconds / MiB |
| --- | --- | --- | --- |
| 10,000 | 0.414 / 35.8 | 0.256 / 35.2 | 1.425 / 106.9 |
| 100,000 | 2.216 / 154.3 | 0.870 / 149.6 | 2.202 / 166.2 |
| 500,000 | 13.905 / 665.3 | 4.172 / 645.3 | 6.073 / 430.8 |

At 500,000 rows per file, the current runtime takes about 70% less time than the previous version and 31% less time than DataComPy in this test. DataComPy uses less memory at that size. The 10,000-row XLSX comparison changed from 3.832 to 3.433 seconds; XLSX profiling changed from 3.631 to 3.811 seconds. Excel parsing remains a substantial cost. The raw records also include CSV profiling results.

These results favor datasets with repeated values and mostly identical rows: 95% of shared rows match exactly. They do not establish performance on high-cardinality columns, mostly changed rows, explicit numeric/date overrides, wide tables, SQL Server, or fuzzy matching. DataComPy receives declared types and uses floating-point numbers; Tie-Out infers types, uses Decimal arithmetic, and produces diagnostic findings. This is a comparison of the documented configurations, not a claim of universal superiority or equivalent feature coverage.

All 57 timed runs passed their expected-count assertions. The current runtime also passed 48 unit tests and the 100-case seeded DataComPy differential check. New regressions cover equal-row validation, stable samples, inference beyond the cache limit, and timestamp tolerance boundaries. Date acceptance now compares integer microseconds against an exact decimal tolerance, avoiding floating-point loss over large date ranges and rounding into acceptance at fractional-day boundaries. Live SQL acceptance was not rerun for this measurement.

To reproduce the comparison, use the [evaluation environment and commands](README.md#run-the-benchmarks-windows). For the previous engine, pass `evaluations/baselines/tie_out_previous.py` to `benchmark.py` with a distinct label. Run the current engine and DataComPy sequentially. Fixture generation is excluded, OS caching is not disabled, and these measurements were not collected in an isolated performance lab.

## Initial study: methodology

Windows 11, Python 3.13.7, Intel Core Ultra 9 285H, 31.4 GiB RAM. Six columns: a zero-padded ID, price, ISO date, currency, quantity, desk. Each side contains N rows; shifting the target ID interval by N/20 creates 95% overlap and 5% missing keys on each side.

In the target, ID modulo 100 below 2 changes price by +1 and date by +1 day; 2–3 changes price by +0.005; 4 changes currency; remaining rows agree. Expected shared-row counts are calculated independently: 95% exact, 2% tolerance, 3% mismatch. Defaults are numeric tolerance 0.01 and date tolerance 0.

Each case runs in three fresh processes. Elapsed times are median process wall times including imports, loading, processing and HTML writing/summary serialization for compare. They exclude fixture generation, the separate profile command, and model/conversation latency. Production functions are called directly, not through CLI argument parsing. Peak memory is the largest Windows peak working set across the three runs. OS caching was not disabled. This was not an isolated performance lab.

## Initial study: results

| Rows per file | Format | Operation | Baseline seconds / MiB | Optimized seconds / MiB |
| --- | --- | --- | --- | --- |
| 10,000 | CSV | Profile | 0.350 / 35.9 | 0.325 / 34.6 |
| 10,000 | CSV | Compare/report | 0.435 / 36.9 | 0.334 / 34.8 |
| 100,000 | CSV | Profile | 1.836 / 157.4 | 1.605 / 145.3 |
| 100,000 | CSV | Compare/report | 2.757 / 166.2 | 2.025 / 154.0 |
| 500,000 | CSV | Profile | 12.568 / 687.0 | 10.390 / 627.0 |
| 500,000 | CSV | Compare/report | 19.333 / 726.2 | 14.977 / 664.8 |
| 10,000 | XLSX | Profile | 3.011 / 60.4 | 3.090 / 60.1 |
| 10,000 | XLSX | Compare/report | 2.956 / 61.9 | 3.023 / 61.4 |

At 500k CSV rows, elapsed time decreased about 23% and peak memory about 8.5%. The changes remove redundant raw-row copies, repeated parsing, and eager type inference. Excel did not meaningfully improve. Profile plus compare at 500k sums to approximately 25.37 seconds before conversation latency. The join still holds both datasets in RAM.

The study included 57 successful timed runs: 24 baseline, 24 optimized, and 9 DataComPy. Each run verified its expected counts; failed runs were excluded from timing statistics. The 17 unit tests and skill metadata validation passed for that implementation. A separate 100-case seeded check agreed with DataComPy on accepted, mismatched, source-only, and target-only counts. Its scope was limited to unique keys, shuffled rows, integer numeric differences, and exact strings.

## Published alternatives: source review

The following feature review was conducted on 2026-09-16. It did not measure assistant execution time or output quality.

| Published work | Observed capability | Comparison with Tie-Out |
| --- | --- | --- |
| [Anthropic reconciliation](https://github.com/anthropics/knowledge-work-plugins/tree/main/finance/skills/reconciliation) | Accounting workflow covering bank, GL/subledger, intercompany, aging and escalation | Broader methodology; inspected skill folder contains instructions. Tie-Out bundles a narrower deterministic export comparison. |
| [Anthropic gl-recon](https://github.com/anthropics/financial-services/blob/main/plugins/agent-plugins/gl-reconciler/skills/gl-recon/SKILL.md) | Business-grain matching, financial break hypotheses, break report and summary | Closest overlap. Its instructions cover composite grain, amount/quantity-specific tolerances and materiality ordering beyond Tie-Out v1. |
| [DataComPy](https://capitalone.github.io/datacompy/pandas_usage.html) | Multiple join columns, absolute/relative tolerances and duplicate handling | Mature engine candidate. Its [report API](https://capitalone.github.io/datacompy/report_api.html) also provides HTML and structured output, so reports alone are not a unique differentiator. |

## DataComPy: executable comparison

DataComPy 1.0.4, pandas 2.3.1, NumPy 2.3.1, same CSV fixtures, absolute tolerance 0.01 and relative tolerance 0. IDs are read as strings; price, quantity and date types are explicitly converted. Each run generates DataComPy's own report with sample limit 50.

| CSV rows per file | Tie-Out seconds / MiB | DataComPy seconds / MiB |
| --- | --- | --- |
| 10,000 | 0.334 / 34.8 | 1.189 / 107.0 |
| 100,000 | 2.025 / 154.0 | 1.925 / 166.0 |
| 500,000 | 14.977 / 664.8 | 5.825 / 432.0 |

DataComPy was faster on the largest workload in this study. The implementations perform different work: Tie-Out infers types, uses Decimal arithmetic, and computes diagnostic patterns; the DataComPy wrapper supplies types and uses floating-point numeric comparison. Both measurements include startup and reporting, so these results apply only to the configurations described here.

## Scope and limitations

These historical measurements apply to the v1 file-comparison implementation only. They do not characterize current SQL Server performance or later comparison features. Current SQL acceptance results and reproduction instructions are in the [evaluation guide](README.md#live-sql-server-acceptance).

No private production exports, wide/long-string stress suite, cold-cache benchmark, million-row XLSX workload, or assistant invocation latency was measured. The differential check covers a defined subset of comparison semantics and is not proof of full equivalence with DataComPy.

Tie-Out provides a lightweight Codex workflow with explicit rules, local computation, and aggregate-only agent context. Any replacement comparison backend should preserve those contracts and pass semantic regression tests.

## Subsequent implementation measurements

The implementation at `b3398e5` includes faster type inference, single-column key indexing, conditional decimal-context widening, and reuse of fuzzy-match target indexes. A 2026-09-22 measurement reported the following results with Python 3.14.6 on Windows 11 (16 logical CPUs, 31.7 GiB RAM), using the same fixtures and three-process median methodology:

| Rows per file | Format | Compare + report | Peak working set |
| --- | --- | --- | --- |
| 10,000 | CSV | 0.25 s | 36 MiB |
| 100,000 | CSV | 1.58 s | 155 MiB |
| 500,000 | CSV | 8.16 s | 665 MiB |
| 10,000 | XLSX | 2.13 s | 51 MiB |

Raw run files were not supplied with these reported measurements. The Python version and environment differ from the initial study, so direct performance comparisons are not supported. Use the [benchmark scripts](README.md#run-the-benchmarks-windows) to reproduce measurements in a specified environment.

## Reproduced benchmark — 2026-09-24

Implementation `b3398e5`, Python 3.13.7, Windows 11; three fresh processes per case. All eight profile/compare cases verified expected counts (24 successful runs).

| Rows per file | Format | Compare + report | Peak working set |
| --- | --- | --- | --- |
| 10,000 | CSV | 0.40 s | 37 MiB |
| 100,000 | CSV | 2.03 s | 156 MiB |
| 500,000 | CSV | 14.77 s | 666 MiB |
| 10,000 | XLSX | 3.36 s | 63 MiB |

[Raw measurements](results/2026-09-24/benchmark.json) include environment, each run, median wall time, and maximum peak working set. Measurements include process startup, input loading, comparison, and report rendering; fixture generation is excluded. These results do not measure SQL Server or fuzzy matching and are not capacity guarantees.
