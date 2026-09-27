# SQL Server integration

[Back to README](../README.md) · [CLI reference](usage.md)

## Setup and example

Either input can be a read-only SQL Server query. Install `pyodbc` and a Microsoft ODBC driver for your platform, then set the connection string in the `TIEOUT_MSSQL_DSN` environment variable. The following PowerShell example uses Windows authentication and verifies the server certificate. Replace the server, database, query, and target file with your own values:

```powershell
python -m pip install -r skills/tie-out/requirements-mssql.txt
$env:TIEOUT_MSSQL_DSN = "Driver={ODBC Driver 18 for SQL Server};Server=yourserver;Database=yourdb;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=no;"
python skills/tie-out/scripts/tie_out.py compare - target.csv --source-query "SELECT trade_id, price, effective_date FROM prices WHERE as_of = '2026-09-16'" --key trade_id --out reports/sql
```

## Query behavior

- Each query must be a single read-only `SELECT` or `WITH` statement.
- `--max-rows` defaults to 1,000,000 rows. A result that exceeds the limit is rejected, not truncated.
- `--timeout` sets the login and query timeout in seconds; the default is 60. Both limits must be positive integers.
- Inputs are read independently. Changes between reads can produce differences even when the underlying systems are consistent; use compatible extraction times or snapshots where possible.
- SQL `DECIMAL` values and text identifiers retain their precision and formatting under the same comparison rules as file inputs.

For automated workflows, use `--fail-on-difference` and handle the documented [exit codes](usage.md#outputs-and-exit-codes).

## Connection and permissions

Use a database account with read-only access to the selected data. The query guard rejects common write statements, but is not a complete SQL parser or a security boundary. SQL Server permissions enforce access.

The environment variable is preferred over `--mssql-dsn`, because command-line credentials may appear in process listings or shell history. The tool does not include connection strings in reports, summaries, or diagnostic output. Keep credentials out of the repository and chat.

`--source-query` and `--target-query` accept one SELECT or read-only WITH statement. A query side uses `-` in place of its positional file path. Both query sides use the same connection string. Worksheet flags apply only to file inputs.

For a local SQLEXPRESS test installation using its self-signed certificate, the [acceptance harness](../evaluations/README.md#live-sql-server-acceptance) documents a local-only certificate-trust example. Remote connections should use a trusted certificate and certificate verification.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Missing SQL dependency | Install the skill's `requirements-mssql.txt` in the Python environment running the script |
| SQL Server operation failed | Check the server/instance, driver, authentication, read permissions, query, and timeout locally; driver diagnostics are intentionally omitted from output |
| Row limit exceeded | Narrow the query or explicitly raise `--max-rows` after checking available memory |
| Duplicate or blank keys | Check what identifies each record and choose a valid single or composite key; duplicate records are not removed automatically |
| Unnamed or repeated columns | Assign a unique alias to every result column |

## Validation status

On 2026-09-17, 17 synthetic integration checks passed against SQL Server 2025 Express 17.0.1000.7 with Windows authentication and ODBC Driver 18. Coverage includes CSV/XLSX comparisons, 38-digit decimal arithmetic, dates, Unicode, NULLs, key validation, row limits, and query errors. See the [recorded results](../evaluations/results/2026-09-17/sql-acceptance.json).

Production data, remote connectivity and TLS, SQL authentication, forced timeout/cancellation, and SQL performance have not been validated by this test suite.
