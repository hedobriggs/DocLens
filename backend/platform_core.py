"""Milestone 1 identity, scoped transactions, and private immutable objects.

Separate from legacy main.py: no fallback to a shared admin or filename corpus.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import os
import secrets
from uuid import UUID

import boto3
from botocore.config import Config
from botocore.session import Session as BotocoreSession
from fastapi import HTTPException
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return 'scrypt$' + salt.hex() + '$' + digest.hex()


def password_matches(password: str, encoded: str) -> bool:
    try:
        algorithm, salt, expected = encoded.split('$')
        if algorithm != 'scrypt':
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class Identity:
    user_id: UUID
    token_digest: str


class Database:
    def __init__(self, runtime_url: str, auth_url: str, *, max_size: int = 4):
        # Context is transaction-local, including when a pooled connection is reused.
        self.pool = ConnectionPool(runtime_url, min_size=0, max_size=max_size, open=True,
                                   kwargs={'row_factory': dict_row}, timeout=10)
        self.auth_url = auth_url
        with self.pool.connection() as conn:
            row = conn.execute("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user").fetchone()
            owner = conn.execute("SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='platform' AND pg_has_role(current_user,c.relowner,'MEMBER') LIMIT 1").fetchone()
            if row['rolsuper'] or row['rolbypassrls'] or owner:
                self.pool.close()
                raise RuntimeError('Platform runtime must be a non-owner, non-bypass role')
            if conn.execute("SELECT has_table_privilege(current_user,'platform.sessions','SELECT') AS auth_access").fetchone()['auth_access']:
                self.pool.close()
                raise RuntimeError('Runtime and identity roles must be separate')
        with self.auth() as conn:
            role = conn.execute("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user").fetchone()
            content = conn.execute("SELECT has_table_privilege(current_user,'platform.documents','SELECT') AS content_access").fetchone()['content_access']
            if role['rolsuper'] or role['rolbypassrls'] or content:
                self.pool.close()
                raise RuntimeError('Identity role must not have content privileges')

    def close(self):
        self.pool.close()

    @contextmanager
    def auth(self):
        with psycopg.connect(self.auth_url, row_factory=dict_row) as conn:
            yield conn

    def identity(self, token: str) -> Identity:
        if not 32 <= len(token) <= 128:
            raise HTTPException(401, 'Sign in required.')
        digest = token_hash(token)
        with self.auth() as conn:
            row = conn.execute('''SELECT s.user_id FROM platform.sessions s JOIN platform.users u ON u.id=s.user_id
              WHERE s.token_hash=%s AND NOT s.revoked AND s.expires_at>now() AND u.active''', (digest,)).fetchone()
        if not row:
            raise HTTPException(401, 'Sign in required.')
        return Identity(row['user_id'], digest)

    def revalidate(self, identity: Identity):
        with self.auth() as conn:
            valid = conn.execute('''SELECT 1 FROM platform.sessions s JOIN platform.users u ON u.id=s.user_id
              WHERE s.token_hash=%s AND s.user_id=%s AND NOT s.revoked AND s.expires_at>now() AND u.active''',
                                 (identity.token_digest, identity.user_id)).fetchone()
        if not valid:
            raise HTTPException(401, 'Sign in required.')

    @contextmanager
    def transaction(self, identity: Identity):
        self.revalidate(identity)
        with self.pool.connection() as conn:
            with conn.transaction():
                conn.execute("SELECT set_config('doclens.principal', %s, true)", (str(identity.user_id),))
                yield conn
                self.revalidate(identity)


def s3_client(*, endpoint: str, access_key: str, secret_key: str):
    """Explicit S3-compatible connection, without machine AWS profiles/files.

    Override sources on this session only. Do not mutate process environment or
    Boto3's default session. Keep SDK TLS verification and AWS_CA_BUNDLE support.
    """
    try:
        if not endpoint or not access_key or not secret_key:
            raise ValueError('Explicit storage connection settings are required')
        session = BotocoreSession(session_vars={
            'profile': (None, None, None, None),
            'config_file': (None, None, os.devnull, None),
            'credentials_file': (None, None, os.devnull, None),
        })
        return boto3.Session(botocore_session=session).client(
            's3', endpoint_url=endpoint, aws_access_key_id=access_key,
            aws_secret_access_key=secret_key, region_name='us-east-1',
            config=Config(signature_version='s3v4', retries={'max_attempts':2},
                          connect_timeout=5, read_timeout=15,
                          s3={'addressing_style':'path'}))
    except Exception as error:
        # SDK errors can embed endpoints, profile names or credential material.
        raise RuntimeError(f'S3-compatible storage initialization failed ({type(error).__name__}).') from None


class Originals:
    def __init__(self, *, endpoint: str, bucket: str, access_key: str, secret_key: str):
        if not endpoint.startswith('https://') and os.getenv('PLATFORM_SYNTHETIC_HTTP') != '1':
            raise RuntimeError('Object storage requires HTTPS; local synthetic tests can opt into HTTP')
        self.bucket = bucket
        self.client = s3_client(endpoint=endpoint, access_key=access_key, secret_key=secret_key)

    def put(self, key: str, data: bytes, *, retention_days=365, legal_hold=False):
        checksum = base64.b64encode(hashlib.sha256(data).digest()).decode()
        # Keys are unpredictable version UUIDs. Also reject any overwrite at storage.
        result = self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType='application/pdf',
                               IfNoneMatch='*', ChecksumSHA256=checksum, ObjectLockMode='COMPLIANCE',
                               ObjectLockRetainUntilDate=datetime.now(timezone.utc)+timedelta(days=retention_days),
                               ObjectLockLegalHoldStatus='ON' if legal_hold else 'OFF')
        if not result.get('VersionId'):
            raise HTTPException(503, 'Object storage must support immutable retained versions.')
        return result['VersionId']

    def get(self, key: str, expected_hash: str, object_version_id: str) -> bytes:
        result = self.client.get_object(Bucket=self.bucket, Key=key, VersionId=object_version_id)
        try:
            data = result['Body'].read(10 * 1024 * 1024 + 1)
        finally:
            result['Body'].close()
        if hashlib.sha256(data).hexdigest() != expected_hash:
            raise HTTPException(503, 'Original integrity check failed.')
        return data


class Embeddings:
    model_id = 'sentence-transformers/all-MiniLM-L6-v2'
    revision = '1110a243fdf4706b3f48f1d95db1a4f5529b4d41'
    name = model_id + '@' + revision

    def __init__(self):
        self.model = None
        from threading import Lock
        self.lock = Lock()

    def encode(self, texts: list[str]) -> list[list[float]]:
        with self.lock:
            if self.model is None:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer(self.model_id, revision=self.revision)
            return self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()
