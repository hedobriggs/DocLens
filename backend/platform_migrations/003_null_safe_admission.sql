-- Preserve applied migration checksums and existing records; reject NULL authority inputs.
CREATE OR REPLACE FUNCTION platform.reserve_ingestion(p_kind text,p_scope uuid,p_key text,p_request_hash text,
 p_document uuid,p_expected uuid,p_hash text,p_bytes integer,p_filename text,p_metadata jsonb,p_manifest jsonb)
RETURNS platform.ingestion_reservations LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,platform,pg_temp AS $$
DECLARE
 r platform.ingestion_reservations; d platform.documents;
 org uuid; ws uuid; lib uuid; days integer; hold boolean; doc uuid; ver uuid; revision bigint;
BEGIN
 IF p_request_hash IS NULL THEN RAISE EXCEPTION USING ERRCODE='DL001',MESSAGE='idempotency_conflict'; END IF;
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
  IF r.actor_id<>platform.principal() OR r.workspace_id IS DISTINCT FROM ws OR r.library_id IS DISTINCT FROM lib OR r.request_sha256 IS DISTINCT FROM p_request_hash THEN
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

CREATE OR REPLACE FUNCTION platform.accept_ingestion(p_reservation uuid,p_token uuid,p_object_version text)
RETURNS platform.ingestion_jobs LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,platform,pg_temp AS $$
DECLARE r platform.ingestion_reservations; s uuid; j platform.ingestion_jobs;
BEGIN
 IF p_token IS NULL THEN RAISE EXCEPTION USING ERRCODE='DL005',MESSAGE='upload_lease_lost'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('doclens.ingestion.admission',0));
 SELECT * INTO r FROM platform.ingestion_reservations WHERE id=p_reservation FOR UPDATE;
 IF NOT FOUND OR r.actor_id<>platform.principal() OR NOT platform.can_scope(r.workspace_id,r.library_id,true) THEN
  RAISE EXCEPTION USING ERRCODE='DL003',MESSAGE='not_found'; END IF;
 IF r.state='accepted' THEN SELECT * INTO j FROM platform.ingestion_jobs WHERE id=r.accepted_job_id; RETURN j; END IF;
 IF r.upload_token IS DISTINCT FROM p_token OR r.lease_expires_at<=clock_timestamp() THEN RAISE EXCEPTION USING ERRCODE='DL005',MESSAGE='upload_lease_lost'; END IF;
 INSERT INTO platform.ingestion_submissions(reservation_id,object_version_id) VALUES(r.id,p_object_version) RETURNING id INTO s;
 INSERT INTO platform.ingestion_jobs(submission_id) VALUES(s) RETURNING * INTO j;
 INSERT INTO platform.ingestion_events(job_id) VALUES(j.id);
 UPDATE platform.ingestion_reservations SET state='accepted',accepted_job_id=j.id,object_version_id=p_object_version WHERE id=r.id;
 RETURN j;
END $$;
ALTER FUNCTION platform.accept_ingestion(uuid,uuid,text) OWNER TO doclens_job_control;
REVOKE ALL ON FUNCTION platform.accept_ingestion(uuid,uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION platform.accept_ingestion(uuid,uuid,text) TO doclens_runtime;

CREATE OR REPLACE FUNCTION platform.release_ingestion(p_reservation uuid,p_token uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,platform,pg_temp AS $$
BEGIN
 IF p_token IS NULL THEN RAISE EXCEPTION USING ERRCODE='DL005',MESSAGE='upload_lease_lost'; END IF;
 UPDATE platform.ingestion_reservations SET lease_expires_at=clock_timestamp()
 WHERE id=p_reservation AND upload_token=p_token AND state='receiving' AND actor_id=platform.principal()
 AND platform.can_scope(workspace_id,library_id,true);
END $$;
ALTER FUNCTION platform.release_ingestion(uuid,uuid) OWNER TO doclens_job_control;
REVOKE ALL ON FUNCTION platform.release_ingestion(uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION platform.release_ingestion(uuid,uuid) TO doclens_runtime;
