"""Developer evaluation harness (Windows peak working set). Not skill runtime.

Run from the repository root; generated data/results stay in .local/performance.
Recorded snapshots in evaluations/results are never overwritten by this script.
"""
import csv
import importlib.util
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
import psutil

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / '.local/performance'
FIELDS = ['id', 'price', 'date', 'currency', 'quantity', 'desk']


def row(i, target):
    price, day, currency = '100.00', '2026-09-01', 'USD'
    if target:
        if i % 100 < 2:
            price, day = '101.00', '2026-09-02'
        elif i % 100 < 4:
            price = '100.005'
        elif i % 100 == 4:
            currency = 'EUR'
    return [f'{i:09d}', price, day, currency, str(i % 200), 'desk_' + str(i % 7)]


def generate(n, fmt):
    folder = BASE / f'{fmt}-{n}'
    folder.mkdir(parents=True, exist_ok=True)
    for target in (False, True):
        p = folder / ('target.' + fmt if target else 'source.' + fmt)
        if p.exists():
            continue
        start = n // 20 if target else 0
        rows = (row(i, target) for i in range(start, start + n))
        if fmt == 'csv':
            with p.open('w', newline='', encoding='utf-8') as handle:
                writer = csv.writer(handle)
                writer.writerow(FIELDS)
                writer.writerows(rows)
        else:
            from openpyxl import Workbook
            book = Workbook(write_only=True)
            sheet = book.create_sheet('Prices')
            sheet.append(FIELDS)
            for r in rows:
                sheet.append(r)
            book.save(p)
            book.close()
    return folder


def worker(script, n, fmt, mode, output):
    started = time.perf_counter()
    spec = importlib.util.spec_from_file_location('engine', script)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    folder = BASE / f'{fmt}-{n}'
    left, right = engine.load(folder / f'source.{fmt}'), engine.load(folder / f'target.{fmt}')
    loaded = time.perf_counter()
    if mode == 'profile':
        lp, rp = engine.profile(*left), engine.profile(*right)
        assert lp['rows'] == rp['rows'] == n
        assert lp['columns']['id']['candidate_key'] and rp['columns']['id']['candidate_key']
        summary = {'source': lp, 'target': rp}
    else:
        summary, detail = engine.reconcile(left, right, 'id')
        shared = n * 19 // 20
        expected = {'shared_keys': shared, 'exact_rows': shared * 95 // 100,
                    'tolerance_rows': shared * 2 // 100, 'mismatched_rows': shared * 3 // 100,
                    'source_only_rows': n // 20, 'target_only_rows': n // 20}
        assert all(summary[k] == v for k, v in expected.items()), (summary, expected)
        assert len(detail['samples']) <= 50
        Path(output).write_text(engine.render(summary, detail), encoding='utf-8')
    encoded = json.dumps(summary)
    finished = time.perf_counter()
    memory = psutil.Process().memory_info()
    print(json.dumps({'load_s': loaded - started, 'work_s': finished - loaded,
                      'total_s': finished - started, 'peak_mib': memory.peak_wset / 2**20,
                      'summary_bytes': len(encoded.encode()), 'correct': True}))


def run(label, script):
    result = {'label': label, 'script': str(script), 'environment': {
        'python': sys.version, 'platform': platform.platform(), 'processor': platform.processor(),
        'logical_cpus': os.cpu_count(), 'ram_gib': psutil.virtual_memory().total / 2**30}, 'cases': []}
    for n, fmt in [(10000, 'csv'), (100000, 'csv'), (500000, 'csv'), (10000, 'xlsx')]:
        folder = generate(n, fmt)
        for mode in ['profile', 'compare']:
            runs = []
            for repeat in range(3):
                output = folder / f'{label}-{mode}-{repeat}.html'
                start = time.perf_counter()
                process = subprocess.run([sys.executable, __file__, 'worker', str(script), str(n), fmt, mode, str(output)], capture_output=True, text=True, timeout=180)
                if process.returncode:
                    raise RuntimeError(process.stderr + process.stdout)
                measured = json.loads(process.stdout)
                measured['process_wall_s'] = time.perf_counter() - start
                runs.append(measured)
            case = {'rows_per_side': n, 'format': fmt, 'mode': mode, 'runs': runs,
                    'median_s': statistics.median(r['process_wall_s'] for r in runs),
                    'peak_mib': max(r['peak_mib'] for r in runs)}
            result['cases'].append(case)
            print(json.dumps({k:v for k,v in case.items() if k != 'runs'}), flush=True)
            (BASE / f'{label}.json').write_text(json.dumps(result, indent=2), encoding='utf-8')


if __name__ == '__main__':
    if sys.platform != 'win32':
        raise SystemExit('This historical benchmark uses Windows peak working set. Run on Windows; do not substitute current RSS for peak memory.')
    if len(sys.argv) < 3:
        raise SystemExit('Usage: python evaluations/scripts/benchmark.py LABEL PATH_TO_ENGINE')
    if sys.argv[1] == 'worker':
        worker(sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5], sys.argv[6])
    else:
        run(sys.argv[1], Path(sys.argv[2]).resolve())
