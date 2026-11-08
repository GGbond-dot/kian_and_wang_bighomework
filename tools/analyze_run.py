import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path


def analyze(path):
    with Path(path).open() as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError('CSV contains no control samples')
    length = sum(math.hypot(float(b['x_m']) - float(a['x_m']), float(b['y_m']) - float(a['y_m'])) for a, b in zip(rows, rows[1:]))
    return {
        'source': str(path),
        'duration_s': float(rows[-1]['time_s']) - float(rows[0]['time_s']),
        'path_length_m': round(length, 4),
        'minimum_front_range_m': min(float(row['front_m']) for row in rows),
        'completed': rows[-1]['state'] == 'DONE',
        'state_samples': dict(Counter(row['state'] for row in rows)),
        'note': 'Front laser distance is not a whole-body collision clearance.',
    }


if __name__ == '__main__':
    print(json.dumps(analyze(sys.argv[1]), indent=2))
