"""Focused regression tests: explicit MinIO configuration must not load AWS profiles."""
import os
from pathlib import Path
import sys
import tempfile
import traceback
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0,str(Path(__file__).resolve().parent))
from acceptance import wait_for_services

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
from platform_core import s3_client


class StoragePortabilityTests(unittest.TestCase):
    def test_nonexistent_profiles_and_malformed_shared_files_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            config=Path(tmp)/'config'; config.write_text('[malformed shared config')
            credentials=Path(tmp)/'credentials'; credentials.write_text('[malformed shared credentials')
            ambient={'AWS_PROFILE':'nonexistent-profile','AWS_DEFAULT_PROFILE':'nonexistent-default',
                     'AWS_CONFIG_FILE':str(config),'AWS_SHARED_CREDENTIALS_FILE':str(credentials),
                     'AWS_ACCESS_KEY_ID':'unrelated-machine-key','AWS_SECRET_ACCESS_KEY':'unrelated-machine-secret',
                     'AWS_SESSION_TOKEN':'unrelated-machine-session','AWS_DEFAULT_REGION':'eu-west-2',
                     'AWS_ENDPOINT_URL_S3':'https://unrelated.invalid'}
            before={name:os.environ.get(name) for name in ambient}
            with patch.dict(os.environ,ambient), patch('boto3.client',side_effect=AssertionError('Default session used')):
                client=s3_client(endpoint='https://minio.example.invalid',access_key='explicit-fixture-key',secret_key='explicit-fixture-secret')
                try:
                    self.assertEqual(client.meta.endpoint_url,'https://minio.example.invalid')
                    self.assertEqual(client.meta.region_name,'us-east-1')
                    self.assertEqual(client.meta.config.signature_version,'s3v4')
                    # Presigning exercises signing with explicit credentials, without network.
                    url=client.generate_presigned_url('get_object',Params={'Bucket':'originals','Key':'fixture'},ExpiresIn=60)
                    self.assertIn('X-Amz-Credential=explicit-fixture-key%2F',url)
                    self.assertNotIn('X-Amz-Security-Token',url)
                    self.assertTrue(client._endpoint.http_session._verify)
                    for name,value in ambient.items(): self.assertEqual(os.environ[name],value)
                finally:
                    client.close()
            self.assertEqual({name:os.environ.get(name) for name in ambient},before)

    def test_shared_default_profile_cannot_change_connection_or_signing(self):
        with tempfile.TemporaryDirectory() as tmp:
            config=Path(tmp)/'config'
            config.write_text('[default]\nregion=eu-west-2\nendpoint_url=https://unrelated.invalid\ns3 =\n    signature_version=unsigned\n    addressing_style=virtual\n')
            credentials=Path(tmp)/'credentials'
            credentials.write_text('[default]\naws_access_key_id=unrelated-machine-key\naws_secret_access_key=unrelated-machine-secret\naws_session_token=unrelated-machine-token\n')
            with patch.dict(os.environ,{'AWS_CONFIG_FILE':str(config),'AWS_SHARED_CREDENTIALS_FILE':str(credentials)}):
                client=s3_client(endpoint='https://minio.example.invalid',access_key='explicit-fixture-key',secret_key='explicit-fixture-secret')
                try:
                    self.assertEqual(client.meta.endpoint_url,'https://minio.example.invalid')
                    self.assertEqual(client.meta.config.s3['addressing_style'],'path')
                    self.assertEqual(client.meta.config.signature_version,'s3v4')
                finally: client.close()

    def test_tls_trust_bundle_remains_configurable(self):
        with patch.dict(os.environ,{'AWS_CA_BUNDLE':'/explicit/trust/bundle.pem'}):
            client=s3_client(endpoint='https://minio.example.invalid',access_key='fixture-key',secret_key='fixture-secret')
            try: self.assertEqual(client._endpoint.http_session._verify,'/explicit/trust/bundle.pem')
            finally: client.close()

    def test_initialization_failure_identifies_component_and_class_without_secret(self):
        with patch('platform_core.BotocoreSession',side_effect=ValueError('secret-endpoint-and-password')):
            try:
                s3_client(endpoint='https://minio.example.invalid',access_key='fixture-key',secret_key='fixture-secret')
            except RuntimeError as error:
                self.assertEqual(str(error),'S3-compatible storage initialization failed (ValueError).')
                rendered=''.join(traceback.format_exception(error))
                self.assertNotIn('secret-endpoint-and-password',rendered)
            else: self.fail('Invalid initialization succeeded')

    def test_missing_explicit_credentials_cannot_fall_back_to_machine_credentials(self):
        with patch.dict(os.environ,{'AWS_ACCESS_KEY_ID':'ambient','AWS_SECRET_ACCESS_KEY':'ambient'}):
            with self.assertRaisesRegex(RuntimeError,r'S3-compatible storage initialization failed \(ValueError\)'):
                s3_client(endpoint='https://minio.example.invalid',access_key='',secret_key='')

    def test_readiness_timeout_identifies_failing_service_without_exception_body(self):
        for component in ('PostgreSQL','MinIO'):
            with self.subTest(component=component):
                client=Mock()
                if component=='PostgreSQL':
                    connection=patch('acceptance.psycopg.connect',side_effect=OSError('sensitive database URL'))
                else:
                    connection=patch('acceptance.psycopg.connect')
                    client.create_bucket.side_effect=ValueError('sensitive storage credential')
                with connection, patch('acceptance.time.monotonic',side_effect=[0,61]):
                    try: wait_for_services('not-used',client)
                    except RuntimeError as error:
                        expected='OSError' if component=='PostgreSQL' else 'ValueError'
                        self.assertEqual(str(error),f'{component} readiness failed ({expected}).')
                        self.assertNotIn('sensitive',''.join(traceback.format_exception(error)))
                    else: self.fail('Failed service was marked ready')


if __name__=='__main__': unittest.main(verbosity=2)
