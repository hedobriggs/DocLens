import json
from pathlib import Path
import re
import runpy
import subprocess
import tempfile
import unittest

PROBE = runpy.run_path(str(Path(__file__).with_name('inspect-omitted-native.py')))['PROBE']

class ProbeChecks(unittest.TestCase):
    def run_probe(self, directory, bounded=False):
        code = re.sub(r'(?m)^roots = .*$', 'roots = [' + repr(str(directory)) + ']', PROBE)
        if bounded:
            code = code.replace('2 * 1024**3', '4')
        r = subprocess.run(['python3', '-c', code], capture_output=True, text=True, check=True)
        return json.loads(r.stdout)

    def test_hash_marker_boundary_and_non_elf(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / 'native').write_bytes(b'\x7fELF' + b'x' * (1024 * 1024 - 9) + b'zipOpenNewFileInZip4_64')
            (p / 'text').write_text('synthetic non-native')
            d = self.run_probe(p)
            self.assertEqual(len(d['files']), 1)
            self.assertIn('zipOpenNewFileInZip4_64', d['files'][0]['markers'])
            self.assertTrue(d['coverage_complete'])

    def test_symlink_is_recorded_not_followed(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / 'alias').symlink_to('/missing-synthetic-target')
            d = self.run_probe(p)
            self.assertEqual(d['symlinks'][0]['target'], '/missing-synthetic-target')
            self.assertEqual(d['files'], [])

    def test_missing_directory_reports_traversal_error(self):
        with tempfile.TemporaryDirectory() as td:
            d = self.run_probe(Path(td) / 'missing')
            self.assertFalse(d['coverage_complete'])
            self.assertEqual(d['errors'][0]['errno'], 2)

    def test_budget_marks_partial_not_success(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / 'native').write_bytes(b'\x7fELF' + b'x' * 100)
            d = self.run_probe(p, bounded=True)
            self.assertIsNotNone(d['bounded_stop'])
            self.assertFalse(d['coverage_complete'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
