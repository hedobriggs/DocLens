"""Offline fixture/oracle tests only; no worker, migration, importer or service.

All examples are hand-authored synthetic snapshots, not a Mac inventory. These
assertions do not establish runtime publication, authorization or data preservation.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]
FIXTURES=Path(__file__).resolve().parent/'fixtures'
BASE='31eb3455cd5dc02c47f343d62328d41c8a2c3458'


def snapshot_digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


class PreservationExamples(unittest.TestCase):
    def setUp(self):
        self.fixture=json.loads((FIXTURES/'preservation.json').read_text())

    def test_original_bytes_hashes_sizes_and_pdf_offsets(self):
        for original in self.fixture['originals']:
            data=(FIXTURES/original['fixture_file']).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(),original['sha256'])
            self.assertEqual(len(data),original['bytes'])
            self.assertIn(original['text'].encode(),data)
            self.assertTrue(data.startswith(b'%PDF-1.4\n'))
            offset=int(data.split(b'startxref\n')[1].splitlines()[0])
            self.assertEqual(data[offset:offset+4],b'xref')
            entries=data[offset:].splitlines()[3:8]
            for number,entry in enumerate(entries,1):
                start=int(entry.split()[0])
                self.assertTrue(data[start:].startswith(f'{number} 0 obj\n'.encode()))

    def test_graph_references_and_exact_excerpt_identity(self):
        platform=self.fixture['platform']
        versions={v['id']:v for v in platform['versions']}
        docs={d['id']:d for d in platform['documents']}
        passages={p['id']:p for p in platform['passages']}
        self.assertEqual(len(versions),len(platform['versions']))
        self.assertEqual(len(passages),len(platform['passages']))
        for doc in docs.values():self.assertEqual(versions[doc['active_version_id']]['document_id'],doc['id'])
        for version in versions.values():self.assertIn(version['document_id'],docs)
        for passage in passages.values():
            self.assertIn(passage['version_id'],versions)
            self.assertEqual(hashlib.sha256(passage['text'].encode()).hexdigest(),passage['excerpt_sha256'])
            self.assertIsNone(passage['coordinates'])
        for citation in self.fixture['citations']:
            passage=passages[citation['passage_id']]
            self.assertEqual(passage['version_id'],citation['version_id'])
            self.assertEqual(passage['excerpt_sha256'],citation['excerpt_sha256'])
            self.assertEqual(versions[citation['version_id']]['sha256'],citation['original_sha256'])
        for event in platform['audit']:self.assertIn(event['version_id'],versions)

    def test_reference_selection_pins_an_approved_library_version(self):
        platform=self.fixture['platform']
        versions={v['id']:v for v in platform['versions']}
        docs={d['id']:d for d in platform['documents']}
        approved={r['version_id'] for r in platform['reference_approvals']}
        self.assertTrue(platform['workspace_references'])
        for selection in platform['workspace_references']:
            self.assertIn(selection['version_id'],approved)
            document=docs[versions[selection['version_id']]['document_id']]
            self.assertIsNotNone(document['library_id']);self.assertIsNone(document['workspace_id'])
            workspace_doc=next(d for d in docs.values() if d['workspace_id']==selection['workspace_id'])
            self.assertEqual(workspace_doc['organisation_id'],document['organisation_id'])

    def test_accepted_job_graph_is_not_a_published_version(self):
        admission=self.fixture['durable_admission']
        reservation=admission['reservations'][0];submission=admission['submissions'][0];job=admission['jobs'][0]
        self.assertEqual(submission['reservation_id'],reservation['id'])
        self.assertEqual(job['submission_id'],submission['id'])
        self.assertEqual(reservation['accepted_job_id'],job['id'])
        self.assertEqual(reservation['object_version_id'],submission['object_version_id'])
        self.assertEqual(admission['events'][0]['job_id'],job['id'])
        self.assertEqual((job['state'],job['stage'],job['attempt_count'],job['lease_generation']),('queued','queued',0,0))
        self.assertNotIn(reservation['version_id'],{v['id'] for v in self.fixture['platform']['versions']})
        self.assertEqual(admission['attempts'],[])

    def test_filename_and_hash_cannot_determine_ownership(self):
        docs=self.fixture['platform']['documents']
        self.assertEqual(docs[0]['filename'],docs[1]['filename'])
        self.assertNotEqual(docs[0]['organisation_id'],docs[1]['organisation_id'])
        self.assertNotEqual(docs[0]['workspace_id'],docs[1]['workspace_id'])
        old=[v for v in self.fixture['platform']['versions'] if v['fixture_file']=='synthetic-old.pdf']
        self.assertGreaterEqual(len(old),2)
        self.assertEqual(old[0]['sha256'],old[1]['sha256'])
        self.assertNotEqual(old[0]['document_id'],old[1]['document_id'])
        self.assertNotEqual(old[0]['object_key'],old[1]['object_key'])

    def test_historical_citation_is_not_the_active_revision(self):
        legacy=self.fixture['legacy'];citation=self.fixture['citations'][0]
        old=next(p for p in legacy['points'] if p['id']==citation['point_id'])
        active=[p for p in legacy['points'] if p['payload']['_doclens_revision']==legacy['catalog']['revision']]
        self.assertEqual(len(active),1)
        self.assertNotEqual(active[0]['id'],old['id'])
        self.assertNotEqual(citation['revision'],legacy['catalog']['revision'])
        doc=next(d for d in self.fixture['platform']['documents'] if d['id']==self.fixture['platform']['versions'][0]['document_id'])
        self.assertNotEqual(citation['version_id'],doc['active_version_id'])

    def test_missing_original_and_ambiguous_source_examples_remain_blocked(self):
        cases={c['case']:c for c in self.fixture['mapping_examples']}
        self.assertIsNone(cases['missing-original']['original_sha256'])
        self.assertIn('original-unavailable',cases['missing-original']['blockers'])
        ambiguous=cases['unknown-owner-same-filename']
        self.assertIsNone(ambiguous['scope_id']);self.assertIsNone(ambiguous['owner_attestation'])
        self.assertIn('ownership-unverified',ambiguous['blockers'])
        self.assertIn('source-version-ambiguous',ambiguous['blockers'])
        for case in cases.values():
            if case['blockers']:
                self.assertEqual(case['expected_gate'],'blocked');self.assertIsNone(case['target_version_id'])
        self.assertEqual(cases['verified-historical-source']['expected_gate'],'eligible-for-separately-approved-rehearsal')

    def test_count_only_oracle_misses_payload_and_identity_changes(self):
        before=self.fixture['legacy']
        for field,value in [('id','rewritten-id'),('vector',[0.0]*384),('payload',{'text':'silently retargeted'})]:
            after=copy.deepcopy(before);after['points'][0][field]=value
            self.assertEqual(len(before['points']),len(after['points']))
            self.assertNotEqual(snapshot_digest(before),snapshot_digest(after))
        reordered=copy.deepcopy(before);reordered['points']=list(reversed(reordered['points']))
        # Point order is not identity. The contract requires ID-keyed comparison.
        normalize=lambda x:sorted(x['points'],key=lambda p:p['id'])
        self.assertEqual(snapshot_digest(normalize(before)),snapshot_digest(normalize(reordered)))

    def test_mutated_original_and_citation_fail_identity_oracles(self):
        original=self.fixture['originals'][0]
        data=(FIXTURES/original['fixture_file']).read_bytes()
        self.assertNotEqual(hashlib.sha256(data+b'changed').hexdigest(),original['sha256'])
        citation=self.fixture['citations'][0];changed=copy.deepcopy(citation)
        changed['version_id']=self.fixture['platform']['documents'][0]['active_version_id']
        self.assertNotEqual(snapshot_digest(citation),snapshot_digest(changed))
        changed=copy.deepcopy(citation);changed['excerpt_sha256']='0'*64
        self.assertNotEqual(snapshot_digest(citation),snapshot_digest(changed))

    def test_vectors_are_explicitly_synthetic_not_model_evidence(self):
        self.assertTrue(self.fixture['legacy']['vectors_are_synthetic'])
        self.assertEqual(self.fixture['kind'],'synthetic-contract-example-only')
        self.assertEqual(self.fixture['baseline'],BASE)
        for point in self.fixture['legacy']['points']:self.assertEqual(len(point['vector']),384)
        self.assertTrue(all(v['embedding_model']=='synthetic-vectors-not-inference/1' for v in self.fixture['platform']['versions']))

    def test_every_baseline_tracked_file_is_byte_identical(self):
        listing=subprocess.check_output(['git','ls-tree','-r','-z',BASE],cwd=ROOT)
        checked=0
        for item in listing.split(b'\0'):
            if not item:continue
            header,name=item.split(b'\t',1);mode,kind,oid=header.split()
            self.assertEqual(kind,b'blob')
            path=ROOT/os.fsdecode(name)
            data=os.fsencode(os.readlink(path)) if mode==b'120000' else path.read_bytes()
            actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest().encode()
            self.assertEqual(actual,oid,os.fsdecode(name));checked+=1
        self.assertGreater(checked,40)


if __name__=='__main__':unittest.main(verbosity=2)
