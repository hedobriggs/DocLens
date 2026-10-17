-- Additive job admission only. No worker, publication, cleanup or DELETE grants.
ALTER TABLE platform.documents ADD COLUMN publication_revision bigint NOT NULL DEFAULT 0 CHECK(publication_revision>=0);
CREATE FUNCTION platform.bump_publication_revision() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 NEW.publication_revision=OLD.publication_revision+1;
 RETURN NEW;
END $$;
CREATE TRIGGER document_publication_revision BEFORE UPDATE OF active_version_id ON platform.documents
 FOR EACH ROW WHEN (OLD.active_version_id IS DISTINCT FROM NEW.active_version_id)
 EXECUTE FUNCTION platform.bump_publication_revision();
REVOKE ALL ON FUNCTION platform.bump_publication_revision() FROM PUBLIC;

-- NOLOGIN admission authority. Its fixed functions expose scoped metadata only.
-- Runtime cannot SET ROLE to it; it has no general RLS bypass.
CREATE ROLE doclens_job_control NOLOGIN NOSUPERUSER NOBYPASSRLS;
GRANT doclens_runtime TO doclens_job_control;
CREATE TABLE platform.ingestion_reservations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), organisation_id uuid NOT NULL REFERENCES platform.organisations,
 workspace_id uuid, library_id uuid, actor_id uuid NOT NULL REFERENCES platform.users,
 idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 16 AND 128),
 request_sha256 text NOT NULL CHECK(request_sha256 ~ '^[0-9a-f]{64}$'),
 document_id uuid NOT NULL, version_id uuid UNIQUE NOT NULL, expected_active_version_id uuid,
 expected_publication_revision bigint CHECK(expected_publication_revision>=0),
 original_sha256 text NOT NULL CHECK(original_sha256 ~ '^[0-9a-f]{64}$'),
 byte_size integer NOT NULL CHECK(byte_size BETWEEN 1 AND 10485760), filename text NOT NULL CHECK(length(filename) BETWEEN 1 AND 255),
 metadata jsonb NOT NULL CHECK(jsonb_typeof(metadata)='object'),
 processing_manifest jsonb NOT NULL CHECK(jsonb_typeof(processing_manifest)='object'),
 object_key text UNIQUE NOT NULL, retention_days integer NOT NULL CHECK(retention_days>=1), legal_hold boolean NOT NULL,
 state text NOT NULL DEFAULT 'receiving' CHECK(state IN ('receiving','accepted')),
 upload_token uuid NOT NULL DEFAULT gen_random_uuid(), lease_expires_at timestamptz NOT NULL DEFAULT now()+interval '15 minutes',
 created_at timestamptz NOT NULL DEFAULT now(), accepted_job_id uuid, object_version_id text,
 CHECK ((workspace_id IS NULL) <> (library_id IS NULL)),
 CHECK ((state='receiving' AND accepted_job_id IS NULL AND object_version_id IS NULL) OR
        (state='accepted' AND accepted_job_id IS NOT NULL AND object_version_id IS NOT NULL)),
 FOREIGN KEY(workspace_id,organisation_id) REFERENCES platform.workspaces(id,organisation_id),
 FOREIGN KEY(library_id,organisation_id) REFERENCES platform.libraries(id,organisation_id),
 FOREIGN KEY(expected_active_version_id,document_id) REFERENCES platform.versions(id,document_id),
 UNIQUE(organisation_id,idempotency_key), UNIQUE(accepted_job_id)
);
CREATE INDEX ingestion_reservation_admission ON platform.ingestion_reservations(state,lease_expires_at,organisation_id);
CREATE TABLE platform.ingestion_submissions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), reservation_id uuid UNIQUE NOT NULL REFERENCES platform.ingestion_reservations,
 object_version_id text NOT NULL CHECK(length(object_version_id)>0), accepted_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE platform.ingestion_jobs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), submission_id uuid UNIQUE NOT NULL REFERENCES platform.ingestion_submissions,
 state text NOT NULL DEFAULT 'queued' CHECK(state IN ('queued','running','retry_wait','succeeded','failed','superseded','cancelled')),
 stage text NOT NULL DEFAULT 'queued' CHECK(stage IN ('queued','extracting','embedding','indexing','publishing','complete')),
 attempt_count integer NOT NULL DEFAULT 0 CHECK(attempt_count BETWEEN 0 AND 3),
 lease_generation bigint NOT NULL DEFAULT 0 CHECK(lease_generation>=0), lease_expires_at timestamptz,
 next_attempt_at timestamptz NOT NULL DEFAULT now(), created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ingestion_jobs_queue ON platform.ingestion_jobs(next_attempt_at,id) WHERE state IN ('queued','retry_wait');
CREATE INDEX ingestion_jobs_active ON platform.ingestion_jobs(id) WHERE state IN ('queued','running','retry_wait');
ALTER TABLE platform.ingestion_reservations ADD FOREIGN KEY(accepted_job_id) REFERENCES platform.ingestion_jobs;
CREATE TABLE platform.ingestion_attempts (
 job_id uuid NOT NULL REFERENCES platform.ingestion_jobs, attempt_no integer NOT NULL CHECK(attempt_no BETWEEN 1 AND 3),
 lease_generation bigint NOT NULL CHECK(lease_generation>0), worker_id uuid NOT NULL,
 started_at timestamptz NOT NULL, finished_at timestamptz NOT NULL CHECK(finished_at>=started_at),
 outcome text NOT NULL CHECK(outcome IN ('succeeded','retryable','failed','superseded','lease_lost','cancelled')),
 error_code text CHECK(error_code IN ('storage_unavailable','database_unavailable','vector_unavailable','invalid_pdf','no_text','resource_limit','permission_revoked','publication_conflict','lease_lost')),
 PRIMARY KEY(job_id,attempt_no)
);
CREATE TABLE platform.ingestion_events (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, job_id uuid NOT NULL REFERENCES platform.ingestion_jobs,
 actor_id uuid NOT NULL DEFAULT platform.principal() REFERENCES platform.users,
 event_type text NOT NULL DEFAULT 'accepted' CHECK(event_type IN ('accepted')), at timestamptz NOT NULL DEFAULT now()
);

GRANT SELECT(id,organisation_id,workspace_id,library_id,actor_id,document_id,version_id,accepted_job_id,state,created_at)
 ON platform.ingestion_reservations TO doclens_runtime;
GRANT SELECT(id,reservation_id,accepted_at) ON platform.ingestion_submissions TO doclens_runtime;
GRANT SELECT ON platform.ingestion_jobs,platform.ingestion_attempts,platform.ingestion_events TO doclens_runtime;
GRANT SELECT ON platform.ingestion_reservations,platform.ingestion_submissions,platform.ingestion_jobs,
 platform.ingestion_attempts,platform.ingestion_events TO doclens_job_control;
GRANT INSERT ON platform.ingestion_reservations,platform.ingestion_submissions,platform.ingestion_jobs,
 platform.ingestion_events TO doclens_job_control;
GRANT UPDATE(upload_token,lease_expires_at,state,accepted_job_id,object_version_id) ON platform.ingestion_reservations TO doclens_job_control;
GRANT USAGE ON SEQUENCE platform.ingestion_events_id_seq TO doclens_job_control;
ALTER TABLE platform.ingestion_reservations ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.ingestion_reservations FORCE ROW LEVEL SECURITY;
CREATE POLICY reservation_read ON platform.ingestion_reservations FOR SELECT TO doclens_runtime
 USING(platform.can_scope(workspace_id,library_id));
CREATE POLICY reservation_control_read ON platform.ingestion_reservations FOR SELECT TO doclens_job_control USING(true);
CREATE POLICY reservation_control_insert ON platform.ingestion_reservations FOR INSERT TO doclens_job_control WITH CHECK(actor_id=platform.principal() AND platform.can_scope(workspace_id,library_id,true));
CREATE POLICY reservation_control_update ON platform.ingestion_reservations FOR UPDATE TO doclens_job_control USING(actor_id=platform.principal() AND platform.can_scope(workspace_id,library_id,true)) WITH CHECK(actor_id=platform.principal() AND platform.can_scope(workspace_id,library_id,true));
ALTER TABLE platform.ingestion_submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.ingestion_submissions FORCE ROW LEVEL SECURITY;
CREATE POLICY submission_read ON platform.ingestion_submissions FOR SELECT TO doclens_runtime USING(EXISTS(
 SELECT 1 FROM platform.ingestion_reservations r WHERE r.id=reservation_id));
CREATE POLICY submission_control_read ON platform.ingestion_submissions FOR SELECT TO doclens_job_control USING(true);
CREATE POLICY submission_control_insert ON platform.ingestion_submissions FOR INSERT TO doclens_job_control WITH CHECK(EXISTS(
 SELECT 1 FROM platform.ingestion_reservations r WHERE r.id=reservation_id AND r.actor_id=platform.principal() AND platform.can_scope(r.workspace_id,r.library_id,true)));
ALTER TABLE platform.ingestion_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.ingestion_jobs FORCE ROW LEVEL SECURITY;
CREATE POLICY job_read ON platform.ingestion_jobs FOR SELECT TO doclens_runtime USING(EXISTS(
 SELECT 1 FROM platform.ingestion_submissions s WHERE s.id=submission_id));
CREATE POLICY job_control_read ON platform.ingestion_jobs FOR SELECT TO doclens_job_control USING(true);
CREATE POLICY job_control_insert ON platform.ingestion_jobs FOR INSERT TO doclens_job_control WITH CHECK(state='queued' AND stage='queued' AND attempt_count=0 AND lease_generation=0 AND lease_expires_at IS NULL AND EXISTS(
 SELECT 1 FROM platform.ingestion_submissions s JOIN platform.ingestion_reservations r ON r.id=s.reservation_id
 WHERE s.id=submission_id AND r.actor_id=platform.principal() AND platform.can_scope(r.workspace_id,r.library_id,true)));
ALTER TABLE platform.ingestion_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.ingestion_attempts FORCE ROW LEVEL SECURITY;
CREATE POLICY attempt_read ON platform.ingestion_attempts FOR SELECT TO doclens_runtime USING(EXISTS(
 SELECT 1 FROM platform.ingestion_jobs j WHERE j.id=job_id));
ALTER TABLE platform.ingestion_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.ingestion_events FORCE ROW LEVEL SECURITY;
CREATE POLICY event_read ON platform.ingestion_events FOR SELECT TO doclens_runtime USING(EXISTS(
 SELECT 1 FROM platform.ingestion_jobs j WHERE j.id=job_id));
CREATE POLICY event_control_insert ON platform.ingestion_events FOR INSERT TO doclens_job_control WITH CHECK(actor_id=platform.principal() AND EXISTS(
 SELECT 1 FROM platform.ingestion_jobs j WHERE j.id=job_id));

CREATE FUNCTION platform.reserve_ingestion(p_kind text,p_scope uuid,p_key text,p_request_hash text,
 p_document uuid,p_expected uuid,p_hash text,p_bytes integer,p_filename text,p_metadata jsonb,p_manifest jsonb)
RETURNS platform.ingestion_reservations LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,platform,pg_temp AS $$
DECLARE
 r platform.ingestion_reservations; d platform.documents;
 org uuid; ws uuid; lib uuid; days integer; hold boolean; doc uuid; ver uuid; revision bigint;
BEGIN
 IF p_kind='workspaces' THEN
  ws=p_scope;
  SELECT organisation_id,retention_days,legal_hold INTO org,days,hold FROM platform.workspaces WHERE id=ws;
 ELSIF p_kind='libraries' THEN
  lib=p_scope; days=365; hold=false;
  SELECT organisation_id INTO org FROM platform.libraries WHERE id=lib;
 ELSE RAISE EXCEPTION USING ERRCODE='DL003',MESSAGE='not_found'; END IF;
 IF org IS NULL OR NOT platform.can_scope(ws,lib,true) THEN
  RAISE EXCEPTION USING ERRCODE='DL003',MESSAGE='not_found'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('doclens.ingestion.admission',0));
 SELECT * INTO r FROM platform.ingestion_reservations WHERE organisation_id=org AND idempotency_key=p_key FOR UPDATE;
 IF FOUND THEN
  IF r.actor_id<>platform.principal() OR r.workspace_id IS DISTINCT FROM ws OR r.library_id IS DISTINCT FROM lib OR r.request_sha256<>p_request_hash THEN
   RAISE EXCEPTION USING ERRCODE='DL001',MESSAGE='idempotency_conflict'; END IF;
  IF r.state='accepted' THEN RETURN r; END IF;
  IF r.lease_expires_at>clock_timestamp() THEN RAISE EXCEPTION USING ERRCODE='DL004',MESSAGE='upload_in_progress'; END IF;
 ELSE
  IF p_document IS NOT NULL THEN
   SELECT * INTO d FROM platform.documents WHERE id=p_document FOR SHARE;
   IF NOT FOUND OR d.workspace_id IS DISTINCT FROM ws OR d.library_id IS DISTINCT FROM lib THEN
    RAISE EXCEPTION USING ERRCODE='DL003',MESSAGE='not_found'; END IF;
   IF d.active_version_id IS DISTINCT FROM p_expected THEN RAISE EXCEPTION USING ERRCODE='DL001',MESSAGE='publication_conflict'; END IF;
   doc=d.id; revision=d.publication_revision;
  ELSE
   IF p_expected IS NOT NULL THEN RAISE EXCEPTION USING ERRCODE='DL001',MESSAGE='publication_conflict'; END IF;
   doc=gen_random_uuid();
  END IF;
 END IF;
 IF (SELECT count(*) FROM platform.ingestion_reservations x WHERE x.state='receiving' AND x.lease_expires_at>clock_timestamp())
  +(SELECT count(*) FROM platform.ingestion_jobs j WHERE j.state IN ('queued','running','retry_wait')) >=32
 OR (SELECT count(*) FROM platform.ingestion_reservations x WHERE x.organisation_id=org AND x.state='receiving' AND x.lease_expires_at>clock_timestamp())
  +(SELECT count(*) FROM platform.ingestion_jobs j JOIN platform.ingestion_reservations x ON x.accepted_job_id=j.id
    WHERE x.organisation_id=org AND j.state IN ('queued','running','retry_wait')) >=8 THEN
  RAISE EXCEPTION USING ERRCODE='DL002',MESSAGE='admission_capacity'; END IF;
 IF r.id IS NOT NULL THEN
  UPDATE platform.ingestion_reservations SET upload_token=gen_random_uuid(),lease_expires_at=clock_timestamp()+interval '15 minutes' WHERE id=r.id RETURNING * INTO r;
 ELSE
  ver=gen_random_uuid();
  INSERT INTO platform.ingestion_reservations(organisation_id,workspace_id,library_id,actor_id,idempotency_key,request_sha256,
    document_id,version_id,expected_active_version_id,expected_publication_revision,original_sha256,byte_size,filename,metadata,processing_manifest,object_key,retention_days,legal_hold)
  VALUES(org,ws,lib,platform.principal(),p_key,p_request_hash,doc,ver,p_expected,revision,p_hash,p_bytes,p_filename,p_metadata,p_manifest,
    org::text||'/'||doc::text||'/'||ver::text||'.pdf',days,hold) RETURNING * INTO r;
 END IF;
 RETURN r;
END $$;
ALTER FUNCTION platform.reserve_ingestion(text,uuid,text,text,uuid,uuid,text,integer,text,jsonb,jsonb) OWNER TO doclens_job_control;
REVOKE ALL ON FUNCTION platform.reserve_ingestion(text,uuid,text,text,uuid,uuid,text,integer,text,jsonb,jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION platform.reserve_ingestion(text,uuid,text,text,uuid,uuid,text,integer,text,jsonb,jsonb) TO doclens_runtime;

CREATE FUNCTION platform.accept_ingestion(p_reservation uuid,p_token uuid,p_object_version text)
RETURNS platform.ingestion_jobs LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,platform,pg_temp AS $$
DECLARE r platform.ingestion_reservations; s uuid; j platform.ingestion_jobs;
BEGIN
 PERFORM pg_advisory_xact_lock(hashtextextended('doclens.ingestion.admission',0));
 SELECT * INTO r FROM platform.ingestion_reservations WHERE id=p_reservation FOR UPDATE;
 IF NOT FOUND OR r.actor_id<>platform.principal() OR NOT platform.can_scope(r.workspace_id,r.library_id,true) THEN
  RAISE EXCEPTION USING ERRCODE='DL003',MESSAGE='not_found'; END IF;
 IF r.state='accepted' THEN SELECT * INTO j FROM platform.ingestion_jobs WHERE id=r.accepted_job_id; RETURN j; END IF;
 IF r.upload_token<>p_token OR r.lease_expires_at<=clock_timestamp() THEN RAISE EXCEPTION USING ERRCODE='DL005',MESSAGE='upload_lease_lost'; END IF;
 INSERT INTO platform.ingestion_submissions(reservation_id,object_version_id) VALUES(r.id,p_object_version) RETURNING id INTO s;
 INSERT INTO platform.ingestion_jobs(submission_id) VALUES(s) RETURNING * INTO j;
 INSERT INTO platform.ingestion_events(job_id) VALUES(j.id);
 UPDATE platform.ingestion_reservations SET state='accepted',accepted_job_id=j.id,object_version_id=p_object_version WHERE id=r.id;
 RETURN j;
END $$;
ALTER FUNCTION platform.accept_ingestion(uuid,uuid,text) OWNER TO doclens_job_control;
REVOKE ALL ON FUNCTION platform.accept_ingestion(uuid,uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION platform.accept_ingestion(uuid,uuid,text) TO doclens_runtime;

CREATE FUNCTION platform.release_ingestion(p_reservation uuid,p_token uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,platform,pg_temp AS $$
BEGIN
 UPDATE platform.ingestion_reservations SET lease_expires_at=clock_timestamp()
 WHERE id=p_reservation AND upload_token=p_token AND state='receiving' AND actor_id=platform.principal()
 AND platform.can_scope(workspace_id,library_id,true);
END $$;
ALTER FUNCTION platform.release_ingestion(uuid,uuid) OWNER TO doclens_job_control;
REVOKE ALL ON FUNCTION platform.release_ingestion(uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION platform.release_ingestion(uuid,uuid) TO doclens_runtime;
