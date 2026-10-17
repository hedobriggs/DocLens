-- Run once with the migration owner, never with an application login.
BEGIN;
CREATE SCHEMA platform;
REVOKE ALL ON SCHEMA platform FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE ROLE doclens_runtime NOLOGIN NOSUPERUSER NOBYPASSRLS;
CREATE ROLE doclens_auth NOLOGIN NOSUPERUSER NOBYPASSRLS;
GRANT USAGE ON SCHEMA platform TO doclens_runtime, doclens_auth;
CREATE TABLE platform.schema_migrations (version integer PRIMARY KEY);
INSERT INTO platform.schema_migrations VALUES (1);
CREATE TABLE platform.users (
 id uuid PRIMARY KEY, email text UNIQUE NOT NULL CHECK (email = lower(email)),
 password_hash text NOT NULL, active boolean NOT NULL DEFAULT true
);
CREATE TABLE platform.sessions (
 token_hash text PRIMARY KEY, user_id uuid NOT NULL REFERENCES platform.users,
 expires_at timestamptz NOT NULL, revoked boolean NOT NULL DEFAULT false
);
CREATE TABLE platform.login_attempts (
 email_hash text PRIMARY KEY, attempts integer NOT NULL, window_start timestamptz NOT NULL
);
GRANT SELECT,INSERT,UPDATE ON platform.login_attempts TO doclens_auth;
CREATE TABLE platform.organisations (id uuid PRIMARY KEY, name text NOT NULL);
CREATE TABLE platform.organisation_memberships (
 organisation_id uuid REFERENCES platform.organisations, user_id uuid REFERENCES platform.users,
 role text NOT NULL CHECK(role IN ('member','admin')), PRIMARY KEY(organisation_id,user_id)
);
CREATE TABLE platform.workspaces (
 id uuid PRIMARY KEY, organisation_id uuid NOT NULL REFERENCES platform.organisations,
 name text NOT NULL, restricted boolean NOT NULL DEFAULT true,
 retention_days integer NOT NULL CHECK(retention_days >= 1), legal_hold boolean NOT NULL DEFAULT false,
 -- Only synthetic documents are admitted by this milestone. No hosted generation.
 processing_policy text NOT NULL DEFAULT 'synthetic-only-no-provider'
 CHECK(processing_policy = 'synthetic-only-no-provider'), UNIQUE(id,organisation_id)
);
CREATE TABLE platform.workspace_memberships (
 workspace_id uuid NOT NULL REFERENCES platform.workspaces, user_id uuid REFERENCES platform.users,
 role text NOT NULL CHECK(role IN ('reader','editor','reviewer','admin')),
 PRIMARY KEY(workspace_id,user_id)
);
CREATE TABLE platform.libraries (
 id uuid PRIMARY KEY, organisation_id uuid NOT NULL REFERENCES platform.organisations,
 name text NOT NULL, rights_basis text NOT NULL CHECK(length(rights_basis)>0),
 reviewed boolean NOT NULL DEFAULT false, UNIQUE(id,organisation_id)
);
CREATE TABLE platform.library_grants (
 library_id uuid REFERENCES platform.libraries, user_id uuid REFERENCES platform.users,
 role text NOT NULL CHECK(role IN ('reader','editor')), PRIMARY KEY(library_id,user_id)
);
CREATE FUNCTION platform.principal() RETURNS uuid LANGUAGE sql STABLE AS
 $$ SELECT nullif(current_setting('doclens.principal', true),'')::uuid $$;
CREATE FUNCTION platform.can_scope(ws uuid, lib uuid, writing boolean DEFAULT false)
 RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT CASE WHEN ws IS NOT NULL AND lib IS NULL THEN EXISTS (
  SELECT 1 FROM platform.workspaces w WHERE w.id=ws AND (NOT writing OR EXISTS (
   SELECT 1 FROM platform.workspace_memberships m WHERE m.workspace_id=w.id
   AND m.user_id=platform.principal() AND m.role IN ('editor','admin'))))
 WHEN lib IS NOT NULL AND ws IS NULL THEN EXISTS (
  SELECT 1 FROM platform.libraries l WHERE l.id=lib AND l.reviewed AND (NOT writing OR EXISTS (
   SELECT 1 FROM platform.library_grants g WHERE g.library_id=l.id
   AND g.user_id=platform.principal() AND g.role='editor')))
 ELSE false END $$;
CREATE TABLE platform.documents (
 id uuid PRIMARY KEY, organisation_id uuid NOT NULL REFERENCES platform.organisations,
 workspace_id uuid, library_id uuid, title text NOT NULL CHECK(length(title) BETWEEN 1 AND 255),
 created_by uuid NOT NULL DEFAULT platform.principal() REFERENCES platform.users,
 active_version_id uuid, CHECK ((workspace_id IS NULL) <> (library_id IS NULL)),
 FOREIGN KEY(workspace_id,organisation_id) REFERENCES platform.workspaces(id,organisation_id),
 FOREIGN KEY(library_id,organisation_id) REFERENCES platform.libraries(id,organisation_id)
);
CREATE TABLE platform.versions (
 id uuid PRIMARY KEY, document_id uuid NOT NULL REFERENCES platform.documents,
 sha256 text NOT NULL CHECK(sha256 ~ '^[0-9a-f]{64}$'), object_key text UNIQUE NOT NULL,
 object_version_id text NOT NULL,
 byte_size integer NOT NULL CHECK(byte_size BETWEEN 1 AND 10485760),
 filename text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 uploader_id uuid NOT NULL DEFAULT platform.principal() REFERENCES platform.users,
 source text NOT NULL CHECK(length(source) BETWEEN 1 AND 1000),
 jurisdiction text NOT NULL CHECK(length(jurisdiction) BETWEEN 1 AND 100),
 effective_date date, received_date date NOT NULL,
 extractor text NOT NULL, chunker text NOT NULL, embedding_model text NOT NULL,
 page_count integer NOT NULL CHECK(page_count BETWEEN 1 AND 100),
 UNIQUE(id,document_id)
);
ALTER TABLE platform.documents ADD CONSTRAINT active_version_belongs_to_document
 FOREIGN KEY(active_version_id,id) REFERENCES platform.versions(id,document_id) DEFERRABLE INITIALLY DEFERRED;
CREATE TABLE platform.passages (
 id uuid PRIMARY KEY, version_id uuid NOT NULL REFERENCES platform.versions,
 page_number integer NOT NULL CHECK(page_number > 0), ordinal integer NOT NULL,
 text text NOT NULL, excerpt_sha256 text NOT NULL, embedding jsonb NOT NULL,
 -- No invented glyph coordinates: page + exact excerpt/hash identify the passage.
 UNIQUE(version_id,ordinal)
);
CREATE TABLE platform.reference_approvals (
 version_id uuid PRIMARY KEY REFERENCES platform.versions,
 reviewed_by uuid NOT NULL REFERENCES platform.users, reviewed_at timestamptz NOT NULL DEFAULT now(),
 source_authority text NOT NULL CHECK(length(source_authority)>0)
);
CREATE TABLE platform.workspace_references (
 workspace_id uuid REFERENCES platform.workspaces, version_id uuid REFERENCES platform.versions,
 PRIMARY KEY(workspace_id,version_id)
);
CREATE TABLE platform.audit_events (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 actor_id uuid NOT NULL DEFAULT platform.principal() REFERENCES platform.users,
 document_id uuid NOT NULL REFERENCES platform.documents,
 version_id uuid, action text NOT NULL CHECK(action IN ('upload','read-original','read-passage','select-reference')),
 at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(version_id,document_id) REFERENCES platform.versions(id,document_id)
);
GRANT SELECT ON platform.users TO doclens_auth;
GRANT SELECT, INSERT, UPDATE ON platform.sessions TO doclens_auth;
GRANT SELECT ON platform.organisations, platform.organisation_memberships,
 platform.workspaces, platform.workspace_memberships, platform.libraries,
 platform.library_grants, platform.documents, platform.versions, platform.passages,
 platform.workspace_references, platform.reference_approvals, platform.audit_events TO doclens_runtime;
GRANT INSERT ON platform.documents, platform.versions, platform.passages,
 platform.workspace_references, platform.audit_events TO doclens_runtime;
GRANT UPDATE(active_version_id) ON platform.documents TO doclens_runtime;
GRANT USAGE ON SEQUENCE platform.audit_events_id_seq TO doclens_runtime;
-- Immutable versions/passages/audit: runtime gets no UPDATE/DELETE grants.
ALTER TABLE platform.organisations ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.organisations FORCE ROW LEVEL SECURITY;
CREATE POLICY org_read ON platform.organisations FOR SELECT USING (EXISTS (
 SELECT 1 FROM platform.organisation_memberships m WHERE m.organisation_id=id AND m.user_id=platform.principal()));
ALTER TABLE platform.organisation_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.organisation_memberships FORCE ROW LEVEL SECURITY;
CREATE POLICY org_member_read ON platform.organisation_memberships FOR SELECT USING(user_id=platform.principal());
ALTER TABLE platform.workspace_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.workspace_memberships FORCE ROW LEVEL SECURITY;
CREATE POLICY ws_member_read ON platform.workspace_memberships FOR SELECT USING(user_id=platform.principal());
ALTER TABLE platform.workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.workspaces FORCE ROW LEVEL SECURITY;
CREATE POLICY ws_read ON platform.workspaces FOR SELECT USING (
 EXISTS (SELECT 1 FROM platform.organisation_memberships m WHERE m.organisation_id=workspaces.organisation_id AND m.user_id=platform.principal())
 AND (NOT restricted OR EXISTS (SELECT 1 FROM platform.workspace_memberships m WHERE m.workspace_id=id AND m.user_id=platform.principal())));
ALTER TABLE platform.library_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.library_grants FORCE ROW LEVEL SECURITY;
CREATE POLICY lib_grant_read ON platform.library_grants FOR SELECT USING(user_id=platform.principal());
ALTER TABLE platform.libraries ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.libraries FORCE ROW LEVEL SECURITY;
CREATE POLICY library_read ON platform.libraries FOR SELECT USING (reviewed AND EXISTS (
 SELECT 1 FROM platform.organisation_memberships m WHERE m.organisation_id=libraries.organisation_id AND m.user_id=platform.principal()) AND EXISTS (
 SELECT 1 FROM platform.library_grants g WHERE g.library_id=id AND g.user_id=platform.principal()));
ALTER TABLE platform.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.documents FORCE ROW LEVEL SECURITY;
CREATE POLICY document_read ON platform.documents FOR SELECT USING(platform.can_scope(workspace_id,library_id));
CREATE POLICY document_insert ON platform.documents FOR INSERT WITH CHECK (
 created_by=platform.principal() AND platform.can_scope(workspace_id,library_id,true));
CREATE POLICY document_update ON platform.documents FOR UPDATE USING(platform.can_scope(workspace_id,library_id,true))
 WITH CHECK(platform.can_scope(workspace_id,library_id,true));
ALTER TABLE platform.versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.versions FORCE ROW LEVEL SECURITY;
CREATE POLICY version_read ON platform.versions FOR SELECT USING(EXISTS (SELECT 1 FROM platform.documents d WHERE d.id=document_id));
CREATE POLICY version_insert ON platform.versions FOR INSERT WITH CHECK(uploader_id=platform.principal() AND EXISTS (
 SELECT 1 FROM platform.documents d WHERE d.id=document_id AND platform.can_scope(d.workspace_id,d.library_id,true)));
ALTER TABLE platform.passages ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.passages FORCE ROW LEVEL SECURITY;
CREATE POLICY passage_read ON platform.passages FOR SELECT USING(EXISTS(SELECT 1 FROM platform.versions v WHERE v.id=version_id));
CREATE POLICY passage_insert ON platform.passages FOR INSERT WITH CHECK(EXISTS (
 SELECT 1 FROM platform.versions v JOIN platform.documents d ON d.id=v.document_id
 WHERE v.id=version_id AND platform.can_scope(d.workspace_id,d.library_id,true)));
ALTER TABLE platform.reference_approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.reference_approvals FORCE ROW LEVEL SECURITY;
CREATE POLICY approval_read ON platform.reference_approvals FOR SELECT USING(EXISTS (
 SELECT 1 FROM platform.versions v JOIN platform.documents d ON d.id=v.document_id WHERE v.id=version_id AND d.library_id IS NOT NULL));
ALTER TABLE platform.workspace_references ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.workspace_references FORCE ROW LEVEL SECURITY;
CREATE POLICY ref_read ON platform.workspace_references FOR SELECT USING (
 platform.can_scope(workspace_id,NULL) AND EXISTS (SELECT 1 FROM platform.reference_approvals a WHERE a.version_id=workspace_references.version_id) AND EXISTS (
 SELECT 1 FROM platform.versions v JOIN platform.documents d ON d.id=v.document_id
 JOIN platform.workspaces w ON w.organisation_id=d.organisation_id
 WHERE v.id=workspace_references.version_id AND w.id=workspace_references.workspace_id AND d.library_id IS NOT NULL));
CREATE POLICY ref_insert ON platform.workspace_references FOR INSERT WITH CHECK (
 platform.can_scope(workspace_id,NULL,true) AND EXISTS (SELECT 1 FROM platform.reference_approvals a WHERE a.version_id=workspace_references.version_id) AND EXISTS (
 SELECT 1 FROM platform.versions v JOIN platform.documents d ON d.id=v.document_id
 JOIN platform.workspaces w ON w.organisation_id=d.organisation_id
 WHERE v.id=workspace_references.version_id AND w.id=workspace_references.workspace_id AND d.library_id IS NOT NULL));
ALTER TABLE platform.audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.audit_events FORCE ROW LEVEL SECURITY;
CREATE POLICY audit_read ON platform.audit_events FOR SELECT USING(EXISTS(SELECT 1 FROM platform.documents d WHERE d.id=document_id));
CREATE POLICY audit_append ON platform.audit_events FOR INSERT WITH CHECK(actor_id=platform.principal() AND EXISTS(SELECT 1 FROM platform.documents d WHERE d.id=document_id));
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA platform FROM PUBLIC;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA platform TO doclens_runtime;
COMMIT;
