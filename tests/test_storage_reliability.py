import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class StorageReliabilityTests(unittest.TestCase):
    def run_scenario(self, name):
        result = subprocess.run([sys.executable, str(ROOT/'tests/storage_scenarios.py'), name], cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_eight_simultaneous_uploads_same_document(self): self.run_scenario('same')
    def test_eight_simultaneous_uploads_different_documents(self): self.run_scenario('different')
    def test_partial_write_preserves_previous_publication(self): self.run_scenario('partial_write')
    def test_failed_publication_preserves_previous_version(self): self.run_scenario('publication_failure')
    def test_retry_restart_counts_and_visibility(self): self.run_scenario('retry_restart')
    def test_existing_unversioned_data_is_preserved_then_replaced(self): self.run_scenario('legacy')
    def test_dense_sixty_page_document(self): self.run_scenario('dense')
    def test_retrieval_and_health_during_failed_replacement(self): self.run_scenario('readers')
    def test_worker_death_before_publication(self): self.run_scenario('process_exit')
    def test_partial_first_upload_stays_invisible(self): self.run_scenario('new_document_failure')
