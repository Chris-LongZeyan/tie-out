import importlib.util
import contextlib
import io
import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/tie-out/scripts/tie_out.py'
spec = importlib.util.spec_from_file_location('tie_out', SCRIPT)
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)


def data(values, fields=('id', 'value')):
    return list(fields), [dict(zip(fields, row)) for row in values]


class ReconciliationTests(unittest.TestCase):
    def test_demo_partition_and_privacy(self):
        root = SCRIPT.parents[3]
        s, detail = t.reconcile(t.load(root/'examples/prices_source.csv'), t.load(root/'examples/prices_target.csv'), 'record_id')
        self.assertEqual([s[k] for k in ('exact_rows', 'tolerance_rows', 'mismatched_rows', 'source_only_rows', 'target_only_rows')], [1, 1, 3, 1, 1])
        self.assertAlmostEqual(s['match_rate'], 2/7)
        self.assertNotIn('samples', s)
        self.assertEqual(len(s['findings']), 3)
        self.assertEqual(len(detail['samples']), 5)

    def test_decimal_boundary(self):
        s, _ = t.reconcile(data([('a', '0.10')]), data([('a', '0.11')]), 'id')
        self.assertEqual(s['tolerance_rows'], 1)

    def test_full_sql_decimal_precision(self):
        value = '123456789012345678901234567890.12345678'
        below = '123456789012345678901234567890.12345677'
        status, delta = t.compare_cell('0', value, 'numeric', Decimal(below), 0)
        self.assertEqual(status, 'numeric_difference')
        self.assertEqual(delta, value)
        status, delta = t.compare_cell(value, '0', 'numeric', Decimal(below), 0)
        self.assertEqual(status, 'numeric_difference')
        self.assertEqual(delta, '-' + value)

    def test_decimal_precision_fast_path_boundary(self):
        status, delta = t.compare_cell('0.123456789012345678901234567', '0.123456789012345678901234568',
                                       'numeric', Decimal(0), 0)
        self.assertEqual(status, 'numeric_difference')
        self.assertEqual(delta, '1E-27')

    def test_duplicates_and_blank_keys_rejected(self):
        for rows in [[('a', '1'), ('a', '2')], [('', '1')], [(' ', '1')]]:
            with self.assertRaises(ValueError):
                t.reconcile(data(rows), data([('a', '1')]), 'id')

    def test_schema_drift(self):
        s, _ = t.reconcile(data([('a', '1', 'x')], ('id', 'value', 'extra')), data([('a', '1')]), 'id')
        self.assertEqual(s['status'], 'differences')

    def test_null_and_literal_na(self):
        s, _ = t.reconcile(data([('a', ''), ('b', 'NA')]), data([('a', ''), ('b', '')]), 'id')
        self.assertEqual(s['exact_rows'], 1)
        self.assertEqual(s['field_stats']['value']['null_mismatch'], 1)

    def test_dates_and_timezones(self):
        self.assertEqual(t.compare_cell('2026-01-01', '2026-01-02', 'date', 0, 1)[0], 'within_tolerance')
        self.assertEqual(t.compare_cell('2026-01-01T00:00:00Z', '2026-01-01T01:00:00+01:00', 'date', 0, 0)[0], 'within_tolerance')
        self.assertEqual(t.compare_cell('2026-01-01', '2026-01-01T00:00:00Z', 'date', 0, 0)[0], 'type_error')

    def test_type_override_preserves_codes(self):
        s, _ = t.reconcile(data([('a', '001')]), data([('a', '1')]), 'id', types={'value': 'string'})
        self.assertEqual(s['mismatched_rows'], 1)

    def test_invalid_declared_type_even_when_equal(self):
        for kind in ('numeric', 'date'):
            with self.subTest(kind=kind):
                s, _ = t.reconcile(data([('a', 'bad')]), data([('a', 'bad')]), 'id', types={'value': kind})
                self.assertEqual(s['field_stats']['value']['type_error'], 1)

    def test_blank_key_not_suggested(self):
        self.assertFalse(t.profile(*data([(' ', '1')]))['columns']['id']['candidate_key'])

    def test_equivalent_offsets_group_together(self):
        s, _ = t.reconcile(data([('a', '1.0'), ('b', '2.00')]), data([('a', '2.0'), ('b', '3.00')]), 'id')
        self.assertEqual(len(s['findings']), 1)
        self.assertIn('2 differing cells', s['findings'][0]['evidence'])

    def test_infer_accepts_single_pass_values(self):
        for values, expected in [(['', '1', '2.5'], 'numeric'), (['2026-01-01', ''], 'date'), (['1', 'bad'], 'string'), ([''], 'string'),
                                 (['1', '2026-01-01'], 'string'), (['2026-01-01', '1'], 'string')]:
            self.assertEqual(t.infer(iter(values)), expected)

    def test_empty_inputs(self):
        s, _ = t.reconcile(data([]), data([]), 'id')
        self.assertIsNone(s['match_rate'])

    def test_nonfinite_tolerances(self):
        for tol in ['NaN', 'Infinity', '-1']:
            with self.assertRaises(ValueError):
                t.reconcile(data([]), data([]), 'id', tol)

    def test_html_escapes_values(self):
        s, d = t.reconcile(data([('a', '<script>alert(1)</script>')]), data([('a', 'b')]), 'id')
        report = t.render(s, d)
        self.assertNotIn('<script>', report)
        self.assertIn('&lt;script&gt;', report)

    def test_csv_identifiers_headers_and_ragged_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/'input.csv'
            p.write_text('id,value\n001,NA\n', encoding='utf-8-sig')
            self.assertEqual(t.load(p)[1][0], {'id': '001', 'value': 'NA'})
            for content in ['id,id\na,b\n', 'id,value\na,b,c\n']:
                p.write_text(content)
                with self.assertRaises(ValueError):
                    t.load(p)

    def test_xlsx_sheets_and_formula_rejection(self):
        from openpyxl import Workbook
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/'input.xlsx'
            book = Workbook()
            book.active.append(['id', 'value'])
            book.active.append(['001', 42])
            book.save(p)
            self.assertEqual(t.load(p)[1][0]['id'], '001')
            book.create_sheet('Other')
            book.save(p)
            with self.assertRaises(ValueError):
                t.load(p)
            self.assertEqual(len(t.load(p, 'Sheet')[1]), 1)
            book['Sheet']['B2'] = '=1+1'
            book.save(p)
            with self.assertRaises(ValueError):
                t.load(p, 'Sheet')
            book.close()

    def test_cli_output_and_no_overwrite(self):
        root = SCRIPT.parents[3]
        with tempfile.TemporaryDirectory() as folder:
            args = ['compare', str(root/'examples/prices_source.csv'), str(root/'examples/prices_target.csv'), '--key', 'record_id', '--out', folder, '--fail-on-difference']
            self.assertEqual(t.main(args), 1)
            self.assertEqual(json.loads((Path(folder)/'summary.json').read_text())['status'], 'differences')
            self.assertEqual(t.main(args), 2)


class ComparisonUpgradeTests(unittest.TestCase):
    def test_equal_rows_preserve_inferred_types_and_counts(self):
        source = data([('a', '1.00', '2026-01-01', 'NA'), ('b', '', '', '')],
                      ('id', 'amount', 'date', 'label'))
        target = (list(reversed(source[0])), list(reversed(source[1])))
        summary, detail = t.reconcile(source, target, 'id')
        self.assertEqual(summary['types'], {'amount': 'numeric', 'date': 'date', 'label': 'string'})
        self.assertEqual(summary['exact_rows'], 2)
        self.assertEqual(summary['status'], 'tied')
        self.assertEqual(summary['field_stats'], {field: {'exact': 2} for field in source[0][1:]})
        self.assertEqual(detail['samples'], [])

    def test_inference_validates_values_after_cache_limit(self):
        values = [str(i) for i in range(5000)]
        self.assertEqual(t.infer(iter(values + values)), 'numeric')
        self.assertEqual(t.infer(iter(values + ['invalid'])), 'string')

    def test_record_loading_preserves_zero_and_false(self):
        headers = ['id', 'value']
        for strings, row, expected in ((True, ['0', '0'], {'id': '0', 'value': '0'}),
                                       (False, [0, False], {'id': '0', 'value': 'False'})):
            with self.subTest(strings=strings):
                _, rows = t.read_records([headers, [], ['', ''], row], strings=strings)
                self.assertEqual(rows, [expected])

    def test_date_tolerance_retains_microseconds_across_centuries(self):
        source = '1000-01-01T00:00:00'
        boundary = '2000-01-01T00:00:00'
        beyond = boundary + '.000001'
        days = Decimal((t.timestamp(boundary) - t.timestamp(source)).days)
        self.assertEqual(t.compare_cell(source, boundary, 'date', 0, days)[0], 'within_tolerance')
        for left, right in ((source, beyond), (beyond, source)):
            with self.subTest(left=left):
                status, delta = t.compare_cell(left, right, 'date', 0, days)
                self.assertEqual(status, 'date_shift')
                self.assertGreater(abs(Decimal(delta)), days)

    def test_date_tolerance_does_not_round_into_acceptance(self):
        source, target = '2026-01-01T00:00:00', '2026-01-01T00:00:00.000001'
        rounded_down = Decimal('0.00000000001157407407407407407407407407')
        self.assertEqual(t.compare_cell(source, target, 'date', 0, rounded_down)[0], 'date_shift')
        rounded_up = Decimal('0.00000000001157407407407407407407407408')
        self.assertEqual(t.compare_cell(source, target, 'date', 0, rounded_up)[0], 'within_tolerance')

    def test_equal_rows_do_not_change_sample_order(self):
        source = data([(f'{i:03}', 'USD') for i in range(200)])
        target = data([(f'{i:03}', 'USD' if i % 2 else 'EUR') for i in reversed(range(200))])
        summary, detail = t.reconcile(source, target, 'id')
        self.assertEqual(summary['exact_rows'], 100)
        self.assertEqual(summary['mismatched_rows'], 100)
        self.assertEqual([sample['key'] for sample in detail['samples']], [f'{i:03}' for i in range(0, 100, 2)])

    def test_tolerances_cannot_be_silently_ignored(self):
        for values, kwargs in (([('a', 'text')], {'column_tolerances': {'value': '1'}}),
                               ([('a', '12')], {'column_days': {'value': '1'}})):
            with self.assertRaisesRegex(ValueError, 'require'):
                t.reconcile(data(values), data(values), 'id', **kwargs)

    def test_date_column_tolerance_boundary(self):
        left, right = data([('a', '2026-01-01')]), data([('a', '2026-01-02')])
        summary, _ = t.reconcile(left, right, 'id', column_days={'value': '1'})
        self.assertEqual(summary['tolerance_rows'], 1)
        summary, _ = t.reconcile(left, right, 'id', column_days={'value': '0.99'})
        self.assertEqual(summary['mismatched_rows'], 1)

    def test_ranked_samples_remain_bounded(self):
        left = data([(str(i).zfill(4), '0') for i in range(500)])
        right = data([(str(i).zfill(4), str(i + 1)) for i in range(500)])
        original = t.heapq.heappush
        sizes = []
        def push(heap, item):
            original(heap, item)
            sizes.append(len(heap))
        with patch.object(t.heapq, 'heappush', side_effect=push):
            summary, detail = t.reconcile(left, right, 'id')
        self.assertEqual(summary['mismatched_rows'], 500)
        self.assertEqual([r['delta'] for r in detail['samples']], [str(i) for i in range(500, 450, -1)])
        self.assertLessEqual(max(sizes), 51)

    def test_composite_key_display_is_unambiguous(self):
        left = data([('a | b', 'c', '1'), ('a', 'b | c', '1')], ('a', 'b', 'v'))
        right = (left[0], [])
        _, detail = t.reconcile(left, right, ['a', 'b'])
        self.assertEqual(len(set(detail['source_only_keys'])), 2)

    def test_per_column_tolerances_override_globals(self):
        left = (['id', 'price', 'fee'], [{'id': 'a', 'price': '1.00', 'fee': '5.00'}])
        right = (['id', 'price', 'fee'], [{'id': 'a', 'price': '1.05', 'fee': '5.50'}])
        s, _ = t.reconcile(left, right, 'id', column_tolerances={'price': '0.10', 'fee': '0.01'})
        self.assertEqual(s['field_stats']['price']['within_tolerance'], 1)
        self.assertEqual(s['field_stats']['fee']['numeric_difference'], 1)
        self.assertIn('numeric_absolute_tolerance_per_column', s['rules'])

    def test_per_column_tolerances_must_be_valid(self):
        for mapping in ({'price': '-1'}, {'price': 'NaN'}, {'nope': '0.1'}):
            with self.assertRaises(ValueError):
                t.reconcile(data([('a', '1')]), data([('a', '1')]), 'id', column_tolerances=mapping)

    def test_composite_key(self):
        left = (['id', 'as_of', 'v'], [{'id': 'a', 'as_of': '2026-01-01', 'v': '1'},
                                        {'id': 'a', 'as_of': '2026-01-02', 'v': '2'}])
        right = (['id', 'as_of', 'v'], [{'id': 'a', 'as_of': '2026-01-01', 'v': '1'},
                                         {'id': 'b', 'as_of': '2026-01-02', 'v': '2'}])
        s, d = t.reconcile(left, right, ['id', 'as_of'])
        self.assertEqual(s['exact_rows'], 1)
        self.assertEqual(s['source_only_rows'], 1)
        self.assertEqual(s['target_only_rows'], 1)
        self.assertEqual(s['key'], ['id', 'as_of'])

    def test_composite_key_rejects_blanks_and_duplicates(self):
        blank = (['id', 'as_of'], [{'id': '', 'as_of': 'x'}])
        with self.assertRaises(ValueError):
            t.reconcile(blank, blank, ['id', 'as_of'])
        dup_left = (['id', 'as_of'], [{'id': 'a', 'as_of': 'x'}, {'id': 'a', 'as_of': 'x'}])
        with self.assertRaises(ValueError):
            t.reconcile(dup_left, (['id', 'as_of'], []), ['id', 'as_of'])

    def test_samples_ranked_by_magnitude(self):
        s, d = t.reconcile(data([('a', '10'), ('b', '100'), ('c', '1000')]),
                           data([('a', '12'), ('b', '101'), ('c', '1002')]), 'id')
        self.assertEqual([row['key'] for row in d['samples']], ['a', 'c', 'b'])

    def test_fuzzy_proposals_do_not_change_counts(self):
        left = (['id', 'v'], [{'id': 'SMITH', 'v': '1'}, {'id': 'JONES', 'v': '2'}])
        right = (['id', 'v'], [{'id': 'SMYTH', 'v': '1'}, {'id': 'BROWN', 'v': '3'}])
        s, d = t.reconcile(left, right, 'id', fuzzy='0.7')
        self.assertEqual(s['source_only_rows'], 2)
        self.assertEqual(s['target_only_rows'], 2)
        self.assertEqual(s['match_rate'], 0)
        self.assertEqual(s['fuzzy']['proposals'], 1)
        self.assertEqual(d['fuzzy_proposals'][0]['source_key'], 'SMITH')
        self.assertEqual(d['fuzzy_proposals'][0]['target_key'], 'SMYTH')

    def test_fuzzy_boundary_threshold_still_proposes(self):
        left = (['id', 'v'], [{'id': 'SMITH', 'v': '1'}])
        right = (['id', 'v'], [{'id': 'SMYTH', 'v': '1'}])
        s, d = t.reconcile(left, right, 'id', fuzzy='0.8')
        self.assertEqual(s['fuzzy']['proposals'], 1)
        self.assertEqual(d['fuzzy_proposals'][0]['similarity'], 0.8)

    def test_fuzzy_disabled_by_default(self):
        s, _ = t.reconcile(data([('SMITH', '1')]), data([('SMYTH', '1')]), 'id')
        self.assertFalse(s['fuzzy']['enabled'])
        self.assertNotIn('fuzzy_proposals', s)

    def test_fuzzy_threshold_validation(self):
        for bad in ('0', '1', '1.5', '-0.5', 'NaN'):
            with self.assertRaises(ValueError):
                t.reconcile(data([('a', '1')]), data([('b', '1')]), 'id', fuzzy=bad)

    def test_fuzzy_skips_large_unmatched_sets(self):
        left = (['id', 'v'], [{'id': f'L{i:05d}', 'v': '1'} for i in range(2100)])
        right = (['id', 'v'], [{'id': f'R{i:05d}', 'v': '1'} for i in range(2000)])
        s, detail = t.reconcile(left, right, 'id', fuzzy='0.8')
        self.assertIn('skipped', s['fuzzy'])
        self.assertNotIn('No pairs above the threshold.', t.render(s, detail))


class FakeCursor:
    def __init__(self, columns, rows):
        self.description = [(c, None, None, None, None, None, None) for c in columns]
        self._rows = list(rows)
        self.query = None
        self.closed = False

    def execute(self, query):
        self.query = query

    def fetchmany(self, size):
        out, self._rows = self._rows[:size], self._rows[size:]
        return out

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, columns, rows):
        self._cursor = FakeCursor(columns, rows)
        self.timeout = None
        self.closed = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.closed = True


class FakePyodbc:
    class Error(Exception):
        pass

    def __init__(self, columns, rows):
        self._columns, self._rows = columns, rows
        self.last_dsn = None
        self.last_timeout = None

    def connect(self, dsn, timeout=None):
        self.last_dsn, self.last_timeout = dsn, timeout
        self.connection = FakeConnection(self._columns, self._rows)
        return self.connection


class SqlInputTests(unittest.TestCase):
    def test_sql_failures_are_sanitized_and_resources_closed(self):
        for stage in ('connect', 'execute', 'fetchmany'):
            fake = self.install(['id', 'value'], [('a', '1')])
            connection = FakeConnection(['id', 'value'], [('a', '1')])
            with contextlib.ExitStack() as stack:
                stack.enter_context(patch.object(fake, 'connect', return_value=connection))
                owner = fake if stage == 'connect' else connection._cursor
                stack.enter_context(patch.object(owner, stage, side_effect=fake.Error('PWD=secret; private query')))
                stderr = stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
                self.assertEqual(t.main(['profile', '--source-query', 'SELECT 1', '--target-query', 'SELECT 1',
                                         '--mssql-dsn', 'DSN=test']), 2)
                self.assertNotIn('secret', stderr.getvalue())
                self.assertIn('SQL Server operation failed', stderr.getvalue())
            if stage != 'connect':
                self.assertTrue(connection.closed)
                self.assertTrue(connection._cursor.closed)

    def test_sql_limits_are_positive(self):
        fake = self.install(['id'], [])
        for limit, timeout in ((0, 30), (-1, 30), (100, 0), (100, -1)):
            with self.assertRaises(ValueError):
                t.load_sql('SELECT id FROM t', 'DSN=test', limit, timeout)
        self.assertIsNone(fake.last_dsn)

    def test_sql_null_rows_are_not_silently_dropped(self):
        fake = self.install(['id', 'value'], [(None, None)])
        result = t.load_sql('SELECT id, value FROM t', 'DSN=test', 100, 30)
        self.assertEqual(len(result[1]), 1)
        with self.assertRaisesRegex(ValueError, 'nonblank'):
            t.reconcile(result, result, 'id')
        self.assertTrue(fake.connection._cursor.closed)
        self.assertTrue(fake.connection.closed)

    def install(self, columns, rows):
        fake = FakePyodbc(columns, rows)
        sys.modules['pyodbc'] = fake
        self.addCleanup(sys.modules.pop, 'pyodbc', None)
        return fake

    def test_readonly_query_guard(self):
        for bad in ('UPDATE t SET x = 1', 'DELETE FROM t', 'SELECT 1; DROP TABLE t',
                    'SELECT 1; SELECT 2', '', 'SELECT * INTO copied FROM t',
                    'WITH x AS (SELECT * FROM t) DELETE FROM x',
                    "SELECT '--'; DELETE FROM t", 'SELECT 1 /* ok */; UPDATE t SET x=2'):
            with self.assertRaises(ValueError):
                t.readonly_query(bad)
        self.assertEqual(t.readonly_query('  WITH x AS (SELECT 1) SELECT * FROM x '), 'WITH x AS (SELECT 1) SELECT * FROM x')
        for query in ("SELECT 'semi;colon', '--', 'it''s fine'", 'SELECT [update], "delete" FROM t;',
                      '/* comment */ SELECT 1 -- comment'):
            self.assertEqual(t.readonly_query(query), query)

    def test_load_sql_converts_values(self):
        fake = self.install(['id', 'price', 'stamp'], [
            ('001', Decimal('100.005'), __import__('datetime').datetime(2026, 1, 1, 12, 0)),
            ('002', None, None),
        ])
        headers, rows = t.load_sql('SELECT id, price, stamp FROM t', 'DSN=demo', 100, 30)
        self.assertEqual(fake.last_dsn, 'DSN=demo')
        self.assertEqual(rows, [{'id': '001', 'price': '100.005', 'stamp': '2026-01-01T12:00:00'},
                                {'id': '002', 'price': '', 'stamp': ''}])

    def test_load_sql_requires_dsn_and_max_rows(self):
        self.install(['id'], [('a',), ('b',)])
        with self.assertRaises(ValueError):
            t.load_sql('SELECT id FROM t', '', 100, 30)
        with self.assertRaises(ValueError):
            t.load_sql('SELECT id FROM t', 'DSN=demo', 1, 30)

    def test_load_sql_rejects_bad_column_names(self):
        self.install(['id', 'id'], [('a', 'b')])
        with self.assertRaises(ValueError):
            t.load_sql('SELECT 1 AS id, 2 AS id', 'DSN=demo', 100, 30)

    def test_cli_sql_side_against_file(self):
        self.install(['id', 'price'], [('001', '100.00'), ('002', '50.00')])
        old = os.environ.get('TIEOUT_MSSQL_DSN')
        os.environ['TIEOUT_MSSQL_DSN'] = 'DSN=demo'
        self.addCleanup(lambda: os.environ.pop('TIEOUT_MSSQL_DSN', None) if old is None
                       else os.environ.__setitem__('TIEOUT_MSSQL_DSN', old))
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'target.csv'
            target.write_text('id,price\n001,100.00\n002,50.005\n', encoding='utf-8')
            args = ['compare', '-', str(target), '--source-query', 'SELECT id, price FROM prices',
                    '--key', 'id', '--out', str(Path(folder) / 'r')]
            self.assertEqual(t.main(args), 0)
            summary = json.loads((Path(folder) / 'r' / 'summary.json').read_text())
            self.assertEqual(summary['exact_rows'], 1)
            self.assertEqual(summary['tolerance_rows'], 1)
            self.assertEqual(summary['status'], 'tied')

    def test_cli_missing_dsn_fails_cleanly(self):
        self.install(['id'], [('a',)])
        old = os.environ.pop('TIEOUT_MSSQL_DSN', None)
        if old is not None:
            self.addCleanup(os.environ.__setitem__, 'TIEOUT_MSSQL_DSN', old)
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'target.csv'
            target.write_text('id,value\na,1\n', encoding='utf-8')
            args = ['compare', '-', str(target), '--source-query', 'SELECT id, value FROM t',
                    '--key', 'id', '--out', str(Path(folder) / 'r')]
            self.assertEqual(t.main(args), 2)


if __name__ == '__main__':
    unittest.main()
