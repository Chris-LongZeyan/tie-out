"""Developer evaluation: seeded DataComPy parity checks. Not skill runtime."""
import importlib.util
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('tieout', ROOT/'skills/tie-out/scripts/tie_out.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)


def main():
    import pandas as pd
    from datacompy.pandas import PandasCompare
    rng = random.Random(20260916)
    fields = ['id', 'amount', 'label']
    for case in range(100):
        left, right = [], []
        for i in range(200):
            a = {'id': f'{i:06d}', 'amount': str(rng.randint(-10000, 10000)), 'label': rng.choice(['USD', 'EUR', 'NA', ' USD'])}
            b = dict(a)
            if rng.random() < .2:
                b['amount'] = str(int(a['amount']) + rng.choice([-2, 1, 4]))
            if rng.random() < .1:
                b['label'] = 'GBP'
            if rng.random() > .1:
                left.append(a)
            if rng.random() > .1:
                right.append(b)
        rng.shuffle(left)
        rng.shuffle(right)
        summary, detail = t.reconcile((fields, left), (fields, right), 'id')
        frames = [pd.DataFrame(rows) for rows in (left, right)]
        for frame in frames:
            frame['amount'] = pd.to_numeric(frame['amount'])
        check = PandasCompare(*frames, join_columns='id', abs_tol=.01, rel_tol=0, cast_column_names_lower=False)
        assert int(check.count_matching_rows()) == summary['exact_rows'] + summary['tolerance_rows']
        assert len(check.df1_unq_rows) == summary['source_only_rows']
        assert len(check.df2_unq_rows) == summary['target_only_rows']
        assert len(check.intersect_rows) - int(check.count_matching_rows()) == summary['mismatched_rows']
        assert summary['source_rows'] == summary['shared_keys'] + summary['source_only_rows']
        assert summary['target_rows'] == summary['shared_keys'] + summary['target_only_rows']
    result = {'seed': 20260916, 'cases': 100, 'keys_per_case': 200, 'status': 'pass',
              'scope': 'unique string keys, integer numeric differences, exact strings, missing rows, shuffled ordering; no assertion of full engine equivalence'}
    output = ROOT/'.local/performance/differential.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
