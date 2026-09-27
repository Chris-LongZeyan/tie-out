"""Developer evaluation: DataComPy comparison, Windows only. Not skill runtime."""
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
import psutil
from benchmark import generate

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / '.local/performance'


def worker(n, output):
    started = time.perf_counter()
    import pandas as pd
    import datacompy
    from datacompy.pandas import PandasCompare
    frames = []
    for side in ['source', 'target']:
        frame = pd.read_csv(BASE / f'csv-{n}' / f'{side}.csv', dtype=str, keep_default_na=False)
        for f in ['price', 'quantity']:
            frame[f] = pd.to_numeric(frame[f])
        frame['date'] = pd.to_datetime(frame['date'])
        frames.append(frame)
    loaded = time.perf_counter()
    comparison = PandasCompare(*frames, join_columns='id', abs_tol=0.01, rel_tol=0,
                               ignore_spaces=False, ignore_case=False, cast_column_names_lower=False)
    matched = int(comparison.count_matching_rows())
    shared = n * 19 // 20
    assert matched == shared * 97 // 100, matched
    assert len(comparison.df1_unq_rows) == len(comparison.df2_unq_rows) == n // 20
    comparison.report(sample_count=50, html_file=str(output))
    finished = time.perf_counter()
    print(json.dumps({'version': datacompy.__version__, 'load_s': loaded-started,
                      'work_s': finished-loaded, 'total_s': finished-started,
                      'peak_mib': psutil.Process().memory_info().peak_wset/2**20,
                      'correct': True, 'matching_rows': matched}))


if __name__ == '__main__':
    if sys.platform != 'win32':
        raise SystemExit('This benchmark uses Windows peak working set; run on Windows.')
    if len(sys.argv) > 1:
        worker(int(sys.argv[1]), sys.argv[2])
    else:
        results = []
        for n in [10000, 100000, 500000]:
            generate(n, 'csv')
            runs = []
            for repeat in range(3):
                output = BASE / f'csv-{n}' / f'datacompy-{repeat}.html'
                start = time.perf_counter()
                proc = subprocess.run([sys.executable, __file__, str(n), str(output)], capture_output=True, text=True, timeout=180)
                if proc.returncode:
                    raise RuntimeError(proc.stderr + proc.stdout)
                measured = json.loads(proc.stdout)
                measured['process_wall_s'] = time.perf_counter()-start
                runs.append(measured)
            result = {'rows_per_side': n, 'runs': runs,
                      'median_s': statistics.median(r['process_wall_s'] for r in runs),
                      'peak_mib': max(r['peak_mib'] for r in runs)}
            results.append(result)
            print(json.dumps({k:v for k,v in result.items() if k != 'runs'}), flush=True)
            (BASE/'datacompy.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
