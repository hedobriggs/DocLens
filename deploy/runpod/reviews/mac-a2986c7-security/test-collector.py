import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('collector', Path(__file__).with_name('collect-native-evidence.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class CollectorSafety(unittest.TestCase):
    def test_missing_folder_stops(self):
        with patch.object(m, 'ROOT', Path('/missing-review-collection-test')), patch.object(m.subprocess, 'check_output') as call:
            with self.assertRaises(SystemExit):
                m.main()
            call.assert_not_called()

    def test_wrong_source_stops(self):
        with tempfile.TemporaryDirectory() as td, patch.object(m, 'ROOT', Path(td)), patch.object(m.subprocess, 'check_output', return_value='wrong') as call:
            with self.assertRaises(SystemExit):
                m.main()
            self.assertEqual(call.call_count, 1)

    def test_wrong_image_stops(self):
        with tempfile.TemporaryDirectory() as td, patch.object(m, 'ROOT', Path(td)), patch.object(m.subprocess, 'check_output', side_effect=[m.SOURCE, 'wrong']), patch.object(m.subprocess, 'run') as run:
            with self.assertRaises(SystemExit):
                m.main()
            run.assert_not_called()

    def test_failed_probe_retains_evidence(self):
        with tempfile.TemporaryDirectory() as td, patch.object(m, 'ROOT', Path(td)), patch.object(m.subprocess, 'check_output', side_effect=[m.SOURCE, m.IMAGE]), patch.object(m.subprocess, 'run', return_value=subprocess.CompletedProcess([], 137)):
            with self.assertRaises(SystemExit):
                m.main()
            folder = next(Path(td).glob('native-assessment.*'))
            self.assertEqual((folder / 'probe.exit').read_text(), '137\n')
            cmd = json.loads((folder / 'commands.json').read_text())['probe_command']
            self.assertIn('--read-only', cmd)
            self.assertIn('--network', cmd)
            self.assertIn('none', cmd)
            self.assertNotIn('--mount', cmd)

if __name__ == '__main__':
    unittest.main(verbosity=2)
