# Evaluation and validation

This directory contains benchmark scripts, integration checks, and dated results. Evaluation dependencies are separate from runtime dependencies; only `skills/tie-out/` is installed as the skill.

## Contents

| Path | Purpose |
| --- | --- |
| `scripts/benchmark.py` | Synthetic fixtures, expected-count validation, and execution-time and memory measurements |
| `scripts/compare_datacompy.py` | DataComPy comparison on the same synthetic CSV fixtures |
| `scripts/differential_check.py` | 100 seeded randomized row-count comparisons against DataComPy |
| `baselines/tie_out_previous.py` | Frozen previous engine used in the 2026-09-27 comparison |
| `baselines/tie_out_7eb451b.py` | Frozen historical engine from commit `7eb451b`; benchmark only, do not maintain as production code |
| `results/2026-09-16/` | Measured baseline/optimized/DataComPy runs and differential result; not newly generated estimates |
| `scripts/sql_acceptance.py` | SELECT-only live SQL Server integration checks |
| `results/2026-09-17/` | Recorded live SQL acceptance results |
| `results/2026-09-24/` | Reproduced benchmark for the optimized runtime |
| `results/2026-09-27/` | Current and previous runtime benchmarks, DataComPy comparison, and regression validation |
| [Assessment](assessment.md) | Method, results, published alternatives, and outstanding validation |

The frozen baseline supports reproducible historical comparisons. Each result applies to the recorded implementation and environment; rerun the scripts to measure a different version or configuration.

## Run the benchmarks (Windows)

Use Python 3.13 for closest comparison to the recorded environment. Create a separate development environment; these dependencies are **not** additional skill runtime requirements.

```powershell
python -m venv .local/evaluation-env
.local/evaluation-env/Scripts/python.exe -m pip install -r evaluations/requirements.txt
.local/evaluation-env/Scripts/python.exe -m unittest discover -s tests -v
.local/evaluation-env/Scripts/python.exe evaluations/scripts/benchmark.py rerun-previous evaluations/baselines/tie_out_previous.py
.local/evaluation-env/Scripts/python.exe evaluations/scripts/benchmark.py rerun-current skills/tie-out/scripts/tie_out.py
.local/evaluation-env/Scripts/python.exe evaluations/scripts/compare_datacompy.py
.local/evaluation-env/Scripts/python.exe evaluations/scripts/differential_check.py
```

Run the commands sequentially from the repository root to avoid competition for CPU and memory. The first run generates CSV/XLSX fixtures under `.local/performance`; subsequent runs reuse them. A complete run processes up to 500,000 rows per input and may take several minutes. Use a unique benchmark label to preserve previous local measurements. The DataComPy and differential scripts replace their local result files.

The timing scripts explicitly require Windows because they measure `peak_wset`. The production skill and unit tests remain portable; the differential script also has no Windows memory dependency. For future Linux/macOS benchmarks, add an explicitly named peak-memory metric and a separate result set, rather than comparing current RSS with Windows peak working set.

Do not run with `python -O`: it disables the assertion-based benchmark correctness checks. Do not replace fixtures with private data: generation assumes this directory contains synthetic fixtures following the documented pattern.

## Result files

Generated datasets, HTML reports, virtual environments, caches, and private exports are excluded from version control. The small JSON snapshots in `results/` record specific validation runs. Review new results for sensitive information before committing them in a dated directory, and retain the original environment and implementation metadata.

## Live SQL Server acceptance

`scripts/sql_acceptance.py` is an opt-in integration harness. It runs synthetic SELECT queries only: no tables, databases, users, or other database objects are created or modified. It writes fresh CSV/XLSX fixtures, reports, and `acceptance.json` under an ignored `.local/sql-acceptance/run-*` directory. It never stores the connection string. Ordinary unit tests do not require SQL Server.

For the local SQLEXPRESS instance, run from PowerShell using an account with access:

```powershell
python -m venv .local/sql-test-env
.local/sql-test-env/Scripts/python.exe -m pip install -r skills/tie-out/requirements.txt -r skills/tie-out/requirements-mssql.txt
$env:TIEOUT_MSSQL_DSN = 'Driver={ODBC Driver 18 for SQL Server};Server=.\SQLEXPRESS;Database=master;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;'
.local/sql-test-env/Scripts/python.exe evaluations/scripts/sql_acceptance.py
Remove-Item Env:TIEOUT_MSSQL_DSN
```

The certificate-trust setting is for this local test instance's self-signed certificate. Remote environments should use a trusted server certificate and certificate verification. No password is needed for this Windows-authentication example.

On 2026-09-17, all 17 checks passed on SQL Server 2025 Express 17.0.1000.7 with Python 3.13.7 and pyodbc 5.3.0. Coverage includes decimal precision, Unicode, leading-zero IDs, NULLs, microsecond SQL timestamps, SQL-to-CSV/XLSX reports, reverse file-to-SQL, composite keys, numeric tolerance boundaries, profile privacy, row limits, empty results, invalid headers/keys, and a real query conversion error. Native Excel dates round to milliseconds, so that case explicitly allows `0.00000001` days (0.864 ms); CSV compares the timestamps exactly. The large decimal is stored as text in Excel to avoid Excel numeric precision loss.

This does not validate production data, remote connectivity/TLS, SQL authentication, least-privilege account provisioning, forced timeout/cancellation, or performance. The harness reads the server's version metadata but does not include its hostname or account name in saved results.

The checks include SQL `DECIMAL(38,8)` arithmetic. The [recorded snapshot](results/2026-09-17/sql-acceptance.json) also includes the unit-test, differential-test, and skill-validation results recorded on that date. It contains no connection string or account identifiers.
