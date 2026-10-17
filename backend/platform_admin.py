"""Explicit offline administration; never imported by request handlers.

Set PLATFORM_OWNER_DATABASE_URL and use `migrate` once on a new database.
No legacy filename corpus is imported. Fixtures are synthetic and opt-in.
"""
import argparse
import hashlib
import re
import os
from pathlib import Path
from uuid import UUID, uuid5, NAMESPACE_URL

import psycopg
from psycopg import sql
from psycopg.pq import TransactionStatus

from platform_core import password_hash


def fixture_id(name):
    return uuid5(NAMESPACE_URL, 'doclens.synthetic/' + name)


def migrate(conn, *, target=None, migrations_dir=None):
    """Atomically apply ordered additive migrations; never reset an existing schema.

    Legacy v1 has no file checksum: record that provenance explicitly rather than
    claiming its executed SQL can be verified retroactively.
    """
    if conn.info.transaction_status != TransactionStatus.IDLE:
        raise RuntimeError('Migrations require an idle owner connection')
    directory=Path(migrations_dir or Path(__file__).parent/'platform_migrations')
    files=sorted(directory.glob('[0-9][0-9][0-9]_*.sql'))
    versions=[int(path.name.split('_',1)[0]) for path in files]
    if not versions or versions!=list(range(1,len(files)+1)):
        raise RuntimeError('Migration files must be unique and contiguous from 001')
    limit=target if target is not None else versions[-1]
    if limit not in versions:
        raise RuntimeError('Unknown migration target')
    original_autocommit=conn.autocommit
    conn.autocommit=True
    try:
        with conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended('doclens.platform.migrations',0))")
            exists=conn.execute("SELECT to_regclass('platform.schema_migrations')").fetchone()[0]
            applied=[r[0] for r in conn.execute('SELECT version FROM platform.schema_migrations ORDER BY version')] if exists else []
            if applied!=list(range(1,len(applied)+1)) or (applied and applied[-1]>limit):
                raise RuntimeError('Migration history is discontinuous or newer than the requested code')
            if not exists and conn.execute("SELECT 1 FROM pg_namespace WHERE nspname='platform'").fetchone():
                raise RuntimeError('Unrecognized platform schema; manual inspection required')
            history=conn.execute("SELECT to_regclass('platform.migration_history')").fetchone()[0]
            if exists and not history:
                conn.execute("""CREATE TABLE platform.migration_history (
                  version integer PRIMARY KEY REFERENCES platform.schema_migrations,
                  sha256 text, provenance text NOT NULL CHECK(provenance IN ('executed','legacy-unverified')),
                  applied_at timestamptz NOT NULL DEFAULT now())""")
                conn.execute("INSERT INTO platform.migration_history(version,sha256,provenance) SELECT version,NULL,'legacy-unverified' FROM platform.schema_migrations")
            for path,version in zip(files,versions):
                content=path.read_text(); checksum=hashlib.sha256(path.read_bytes()).hexdigest()
                if version in applied:
                    row=conn.execute('SELECT sha256 FROM platform.migration_history WHERE version=%s',(version,)).fetchone()
                    if not row or (row[0] is not None and row[0]!=checksum):
                        raise RuntimeError('An applied migration checksum changed')
                    continue
                if version>limit: break
                if version==1:
                    # Preserve the original file byte-for-byte; the runner owns its transaction.
                    content=re.sub(r'^BEGIN;\s*$', '', content, count=1, flags=re.MULTILINE)
                    content=re.sub(r'^COMMIT;\s*$', '', content, count=1, flags=re.MULTILINE)
                if re.search(r'^\s*(COMMIT|ROLLBACK|START\s+TRANSACTION)\b',content,re.MULTILINE|re.IGNORECASE):
                    raise RuntimeError('Migration scripts must not control transactions')
                conn.execute(content)
                if version==1:
                    conn.execute("""CREATE TABLE platform.migration_history (
                      version integer PRIMARY KEY REFERENCES platform.schema_migrations,
                      sha256 text, provenance text NOT NULL CHECK(provenance IN ('executed','legacy-unverified')),
                      applied_at timestamptz NOT NULL DEFAULT now())""")
                else:
                    conn.execute('INSERT INTO platform.schema_migrations VALUES (%s)',(version,))
                conn.execute("INSERT INTO platform.migration_history(version,sha256,provenance) VALUES (%s,%s,'executed')",(version,checksum))
    finally:
        conn.autocommit=original_autocommit


def logins(conn, runtime_password, auth_password):
    for name, group, password in [('doclens_web','doclens_runtime',runtime_password), ('doclens_identity','doclens_auth',auth_password)]:
        conn.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD {} IN ROLE {}').format(
            sql.Identifier(name),sql.Literal(password),sql.Identifier(group)))


def seed_synthetic(conn, password):
    """Two firms; two restricted A workspaces; explicit grants, no implicit admin."""
    for firm in ('firm-a','firm-b'):
        conn.execute('INSERT INTO platform.organisations VALUES (%s,%s)', (fixture_id(firm),firm))
    for user in ('alice','bob','carol','org-admin','reader','reviewer'):
        conn.execute('INSERT INTO platform.users(id,email,password_hash) VALUES (%s,%s,%s)',
                     (fixture_id(user),f'{user}@synthetic.invalid',password_hash(password)))
        firm='firm-b' if user=='bob' else 'firm-a'
        conn.execute('INSERT INTO platform.organisation_memberships VALUES (%s,%s,%s)',
                     (fixture_id(firm),fixture_id(user),'admin' if user=='org-admin' else 'member'))
    for name,firm in [('a-private','firm-a'),('a-restricted','firm-a'),('b-private','firm-b')]:
        conn.execute('''INSERT INTO platform.workspaces(id,organisation_id,name,restricted,retention_days,legal_hold)
                        VALUES (%s,%s,%s,true,365,false)''', (fixture_id(name),fixture_id(firm),name))
    for user,ws,role in [('alice','a-private','editor'),('carol','a-restricted','admin'),('bob','b-private','editor'),
                         ('reader','a-private','reader'),('reviewer','a-private','reviewer')]:
        conn.execute('INSERT INTO platform.workspace_memberships VALUES (%s,%s,%s)',(fixture_id(ws),fixture_id(user),role))
    for name,firm,user in [('a-library','firm-a','alice'),('b-library','firm-b','bob')]:
        conn.execute('INSERT INTO platform.libraries VALUES (%s,%s,%s,%s,true)',
                     (fixture_id(name),fixture_id(firm),name,'Synthetic author-owned fixture'))
        conn.execute('INSERT INTO platform.library_grants VALUES (%s,%s,%s)', (fixture_id(name),fixture_id(user),'editor'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['migrate','create-logins','seed-synthetic'])
    parser.add_argument('--confirm-synthetic', action='store_true')
    args=parser.parse_args()
    with psycopg.connect(os.environ['PLATFORM_OWNER_DATABASE_URL'],autocommit=True) as conn:
        if args.command=='migrate':
            migrate(conn)
        elif args.command=='create-logins':
            logins(conn,os.environ['PLATFORM_RUNTIME_PASSWORD'],os.environ['PLATFORM_AUTH_PASSWORD'])
        else:
            if not args.confirm_synthetic:
                parser.error('Synthetic fixture creation requires --confirm-synthetic')
            with conn.transaction():
                seed_synthetic(conn,os.environ['PLATFORM_FIXTURE_PASSWORD'])


if __name__=='__main__':
    main()
