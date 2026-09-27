"""Opt-in live SQL Server acceptance checks using only synthetic SELECT results.

Set TIEOUT_MSSQL_DSN locally. Never prints or saves the connection string.
Creates local fixtures/reports only; does not create or change database objects.
"""
import contextlib
import csv
import importlib.util
import io
import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path
import tempfile

import pyodbc
from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('tie_out', ROOT / 'skills/tie-out/scripts/tie_out.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)

QUERY = """SELECT id, amount, stamp, label FROM (VALUES
('001', CAST('12345678901234567890.123456' AS decimal(28,6)),
 CAST('2026-09-17T12:34:56.123456' AS datetime2(6)), N'测试'),
('002', CAST('50' AS decimal(28,6)), CAST('2026-09-18' AS datetime2(6)), N'USD'),
('003', CAST(NULL AS decimal(28,6)), CAST(NULL AS datetime2(6)), CAST(NULL AS nvarchar(10)))
) AS fixture(id, amount, stamp, label)"""
HEADERS = ['id', 'amount', 'stamp', 'label']
ROWS = [
    ['001', '12345678901234567890.123456', '2026-09-17T12:34:56.123456', '测试'],
    ['002', '50.000000', '2026-09-18T00:00:00', 'USD'],
    ['003', '', '', ''],
]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    dsn = os.environ.get('TIEOUT_MSSQL_DSN')
    if not dsn:
        raise SystemExit('Set TIEOUT_MSSQL_DSN locally before running live acceptance checks.')
    parent = ROOT / '.local/sql-acceptance'
    parent.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='run-', dir=parent))
    checks = []

    def checked(name):
        checks.append(name)
        print('PASS:', name)

    def run_cli(name, args, expected=0):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = t.main(args)
        require(code == expected, f'{name}: unexpected exit code {code}')
        require(dsn not in stdout.getvalue() + stderr.getvalue(), 'Connection string appeared in output')
        if code == 2:
            require(not (out / name / 'summary.json').exists(), 'Failed run produced a summary')
        checked(name)
        return json.loads(stdout.getvalue()) if stdout.getvalue() else None

    try:
        with pyodbc.connect(dsn, timeout=10) as connection:
            version, edition = connection.execute(
                "SELECT CAST(SERVERPROPERTY('ProductVersion') AS varchar(50)), "
                "CAST(SERVERPROPERTY('Edition') AS varchar(100))").fetchone()
            driver = connection.getinfo(pyodbc.SQL_DRIVER_NAME)
            driver_version = connection.getinfo(pyodbc.SQL_DRIVER_VER)
        connection.close()
        loaded = t.load_sql(QUERY, dsn, 3, 10)
        require(loaded == (HEADERS, [dict(zip(HEADERS, row)) for row in ROWS]),
                'SQL values lost precision, Unicode, leading zeros, dates, or NULL semantics')
        checked('sql_type_preservation_and_exact_row_limit')

        wide = t.load_sql("SELECT '001' AS id, CAST('123456789012345678901234567890.12345678' "
                          "AS decimal(38,8)) AS amount", dsn, 1, 10)
        zero = (['id', 'amount'], [{'id': '001', 'amount': '0'}])
        summary, detail = t.reconcile(zero, wide, 'id',
                                      numeric_tolerance='123456789012345678901234567890.12345677')
        require(summary['mismatched_rows'] == 1 and
                detail['samples'][0]['delta'] == '123456789012345678901234567890.12345678',
                'SQL decimal(38,8) difference was rounded')
        checked('sql_decimal_38_digit_difference')

        csv_path, xlsx_path = out / 'target.csv', out / 'target.xlsx'
        with csv_path.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerows([HEADERS, *ROWS])
        book = Workbook()
        book.active.append(HEADERS)
        for original in ROWS:
            row = list(original)
            if row[2]:
                row[2] = datetime.fromisoformat(row[2])
            book.active.append(row)
        book.save(xlsx_path)
        book.close()
        for kind, path in (('csv', csv_path), ('xlsx', xlsx_path)):
            name = 'sql_to_' + kind
            args = ['compare', '-', str(path), '--source-query', QUERY, '--key', 'id',
                    '--out', str(out / name), '--fail-on-difference']
            if kind == 'xlsx':
                args += ['--date-tolerance', 'stamp=0.00000001']
            payload = run_cli(name, args)
            summary = payload['summary']
            require(summary['status'] == 'tied' and summary['shared_keys'] == 3,
                    name + ': expected three accepted rows')
            require((out / name / 'report.html').is_file(), name + ': missing HTML report')
            require('12345678901234567890' not in json.dumps(summary), 'Row values leaked into summary')

        payload = run_cli('file_to_sql', ['compare', str(csv_path), '-', '--target-query', QUERY,
                                         '--key', 'id', '--out', str(out / 'file_to_sql')])
        require(payload['summary']['exact_rows'] == 3, 'Reverse comparison differs')
        payload = run_cli('composite_sql_to_sql', ['compare', '--source-query', QUERY,
                         '--target-query', QUERY, '--key', 'id,amount',
                         '--out', str(out / 'composite_sql_to_sql')], expected=2)
        valid_query = QUERY + " WHERE id <> '003'"
        payload = run_cli('valid_composite_sql_to_sql', ['compare', '--source-query', valid_query,
                         '--target-query', valid_query, '--key', 'id,amount',
                         '--out', str(out / 'valid_composite_sql_to_sql')])
        require(payload['summary']['exact_rows'] == 2, 'Composite SQL join differs')

        changed = QUERY.replace("CAST('50' AS", "CAST('50.01' AS")
        payload = run_cli('numeric_boundary', ['compare', '-', str(csv_path), '--source-query', changed,
                         '--key', 'id', '--out', str(out / 'numeric_boundary'), '--fail-on-difference'])
        require(payload['summary']['tolerance_rows'] == 1, 'Inclusive numeric tolerance failed')
        changed = QUERY.replace("CAST('50' AS", "CAST('50.02' AS")
        payload = run_cli('numeric_difference', ['compare', '-', str(csv_path), '--source-query', changed,
                         '--key', 'id', '--out', str(out / 'numeric_difference'), '--fail-on-difference'], 1)
        require(payload['summary']['mismatched_rows'] == 1, 'Numeric mismatch not detected')
        payload = run_cli('profile', ['profile', '-', str(csv_path), '--source-query', QUERY])
        require('12345678901234567890' not in json.dumps(payload), 'Row value leaked into profile')

        for name, query, extra in (
            ('row_limit', QUERY, ['--max-rows', '2']),
            ('query_error', 'SELECT CAST(N\'not-a-number\' AS int) AS value', []),
            ('unnamed_column', 'SELECT 1', []),
            ('duplicate_column', 'SELECT 1 AS id, 2 AS id', []),
            ('blank_key', "SELECT CAST(NULL AS varchar(10)) AS id, CAST(NULL AS int) AS value", []),
            ('duplicate_key', "SELECT id, value FROM (VALUES ('a', 1), ('a', 2)) AS f(id, value)", []),
        ):
            run_cli(name, ['compare', '-', str(csv_path), '--source-query', query, '--key', 'id',
                          '--out', str(out / name), *extra], 2)
        empty = t.load_sql(QUERY + ' WHERE 1 = 0', dsn, 3, 10)
        summary, _ = t.reconcile(empty, empty, 'id')
        require(summary['match_rate'] is None and summary['source_rows'] == 0, 'Empty result semantics failed')
        checked('empty_result')
        result = {'status': 'pass', 'created_utc': datetime.now(timezone.utc).isoformat(),
                  'python': platform.python_version(), 'server_version': version, 'edition': edition,
                  'driver': driver, 'driver_version': driver_version, 'checks': checks,
                  'scope': 'Synthetic SELECT-only queries; no database objects created or modified.',
                  'limitations': 'No production data, remote/TLS validation, SQL authentication, forced timeout, or performance testing.'}
        (out / 'acceptance.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(f'Passed {len(checks)} checks. Results: {out / "acceptance.json"}')
    except pyodbc.Error:
        raise SystemExit('Live SQL connection failed; inspect connection settings locally. Driver details omitted.') from None


if __name__ == '__main__':
    main()
