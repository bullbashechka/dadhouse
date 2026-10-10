import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from stage1 import mm_to_m, validate_spec


class DataContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'drawing.pdf').write_bytes(b'fixture')
        self.spec = {
            'schema_version': 1, 'linear_unit': 'mm',
            'sources': [{'id': 'pdf', 'path': 'drawing.pdf',
                         'sha256': hashlib.sha256(b'fixture').hexdigest()}],
            'rooms': [{'id': n} for n in range(1, 13)],
            'measurements': [{'id': 'test', 'value': 5000, 'unit': 'mm',
                              'status': 'dimensioned', 'source': 'pdf',
                              'page': 2, 'check_range': [5000, 5000]}],
        }

    def test_known_lengths(self):
        for value, expected in [(1000, 1), (5000, 5), (5300, 5.3), (-600, -0.6)]:
            self.assertEqual(mm_to_m(value), expected)

    def test_valid_sources_and_dimensions(self):
        self.assertEqual(validate_spec(self.spec, self.root), [])

    def test_rejects_wrong_units(self):
        self.spec['linear_unit'] = 'm'
        self.assertTrue(any('linear_unit' in x for x in validate_spec(self.spec, self.root)))

    def test_rejects_missing_source(self):
        (self.root / 'drawing.pdf').unlink()
        self.assertTrue(any('missing source' in x for x in validate_spec(self.spec, self.root)))

    def test_rejects_changed_source(self):
        (self.root / 'drawing.pdf').write_bytes(b'changed')
        self.assertTrue(any('checksum' in x for x in validate_spec(self.spec, self.root)))

    def test_unknown_requires_reason(self):
        item = self.spec['measurements'][0]
        item.update(value=None, status='unknown', check_range=None)
        self.assertTrue(any('reason' in x for x in validate_spec(self.spec, self.root)))
        item['reason'] = 'No dimension in drawing'
        self.assertEqual(validate_spec(self.spec, self.root), [])

    def test_rejects_out_of_range(self):
        self.spec['measurements'][0]['check_range'] = [5100, 5200]
        self.assertTrue(any('range' in x for x in validate_spec(self.spec, self.root)))

    def test_requires_all_room_ids(self):
        self.spec['rooms'][-1]['id'] = 11
        self.assertTrue(any('rooms' in x for x in validate_spec(self.spec, self.root)))


if __name__ == '__main__':
    unittest.main()
