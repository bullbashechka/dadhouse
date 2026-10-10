"""Validate the stage 1 source register using Python's standard library."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mm_to_m(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Expected a finite length in millimetres')
    return value / 1000


def validate_spec(spec, root=ROOT):
    errors = []
    if spec.get('schema_version') != 1:
        errors.append('schema_version: expected 1')
    if spec.get('linear_unit') != 'mm':
        errors.append('linear_unit: expected mm')
    sources = spec.get('sources', [])
    source_ids = [s['id'] for s in sources]
    if not sources or len(set(source_ids)) != len(source_ids):
        errors.append('sources: empty or duplicate identifiers')
    for source in sources:
        path = (root / source['path']).resolve()
        if not path.is_relative_to(root.resolve()):
            errors.append(f"source outside project: {source['id']}")
        elif not path.is_file():
            errors.append(f"missing source: {source['id']}")
        elif sha256(path) != source['sha256']:
            errors.append(f"checksum mismatch: {source['id']}")
    if sorted(room['id'] for room in spec.get('rooms', [])) != list(range(1, 13)):
        errors.append('rooms: expected unique explication IDs 1–12')
    seen = set()
    for item in spec.get('measurements', []):
        key = item['id']
        if key in seen:
            errors.append(f'{key}: duplicate measurement')
        seen.add(key)
        if item.get('source') not in source_ids:
            errors.append(f'{key}: unknown source')
        if item.get('source') == 'pdf' and item.get('page') not in (1, 2, 3):
            errors.append(f'{key}: missing PDF page')
        if item.get('unit') not in ('mm', 'm2', 'degrees'):
            errors.append(f'{key}: invalid unit')
        status = item.get('status')
        if status not in ('dimensioned', 'reconstructed', 'assumption', 'unknown', 'agreed'):
            errors.append(f'{key}: invalid status')
        value = item.get('value')
        if status == 'unknown':
            if value is not None or not item.get('reason') or item.get('check_range') is not None:
                errors.append(f'{key}: unknown needs null value/range and reason')
        elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            errors.append(f'{key}: expected finite numeric value')
        else:
            bounds = item.get('check_range')
            if not isinstance(bounds, list) or len(bounds) != 2 or not bounds[0] <= value <= bounds[1]:
                errors.append(f'{key}: invalid check range')
    return errors


def main():
    spec_path = ROOT / 'data/house_spec.json'
    spec = json.loads(spec_path.read_text())
    errors = validate_spec(spec)
    result = {'ok': not errors, 'errors': errors, 'spec_sha256': sha256(spec_path),
              'source_count': len(spec['sources']), 'room_count': len(spec['rooms']),
              'measurement_count': len(spec['measurements'])}
    (ROOT / 'data/data_validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(bool(errors))


if __name__ == '__main__':
    main()
