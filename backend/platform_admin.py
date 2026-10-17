"""Explicit offline administration; never imported by request handlers.

Set PLATFORM_OWNER_DATABASE_URL and use `migrate` once on a new database.
No legacy filename corpus is imported. Fixtures are synthetic and opt-in.
"""
import argparse
import os
from pathlib import Path
from uuid import UUID, uuid5, NAMESPACE_URL

import psycopg
from psycopg import sql

from platform_core import password_hash


def fixture_id(name):
    return uuid5(NAMESPACE_URL, 'doclens.synthetic/' + name)


def migrate(conn):
    conn.execute((Path(__file__).parent/'platform_migrations/001_foundation.sql').read_text())


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
