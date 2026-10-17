# Frontend recovery correction — independent review pending

Helper base: `f2142166fd54c06786d16ce7fb55f4519a7d0824`.
Application source remains pinned to reviewed commit
`76b81c1bf5a23fd62e344e893b1bff45e24e8cb4`; no application files change here.
Do not resume the Mac update until this helper correction is independently
reviewed and the user authorizes resumption. No merge or deployment is included.

## Reported failure and preserved state

The running Mac `doclens-frontend` references unavailable image
`sha256:6a4c15d7aeac049beeb8e8c94e222908319aff9399127a6d2dc053c2565caf09`.
The available `doclens-frontend:latest` is different and must not be substituted.
Backend tagging succeeded, but the old helper saved image-tag progress only after
both services. Services remain running; source and Qdrant have not been updated.

Existing private backup:
`/Users/nnamdihedo/Desktop/DocLens-backup-20261017-232914`.
Keep this directory and its old state, helper, checkout archive, credentials, and
any successful backend backup tag. No overwrite or automatic restart is proposed.

## New behavior

`preserve-frontend --backup <existing-private-backup> --expected-frontend-image <reported-ID>`
is a capture-only phase for
that old `backup-started` state. It creates a new UUID-named private child directory,
leaves the original backup files untouched, and does not apply source changes,
stop/recreate services, rebuild, or touch Qdrant. The original frontend is paused
briefly while its filesystem and mounted data are captured, then unpaused in a
`finally` block, before any recovery image is constructed or tested. Capture time
can be substantial for a large filesystem. A failed unpause is an explicit stop
requiring operator attention; the helper cannot guarantee recovery from a daemon
failure. An already paused or stopped source container is rejected.

The full root filesystem is streamed from `docker export <container-ID>` into a
private tar file. This avoids requiring the missing image as a parent. The
original container ID, image ID, configuration, mounts, and running state are
checked. Runtime platform/architecture come from the original Node process.
**A container export alone excludes mounts and loses image runtime configuration;
it is not advertised as a complete image backup.**

For supported bind and volume mounts, the helper requires an explicit
`--quiescent-mounts` declaration after the owner has stopped all outside writers.
Pausing frontend processes cannot quiesce host processes or other containers.
Each mount is copied twice while paused; differing archives fail capture.
This comparison can detect observed changes but is not a transactional filesystem
snapshot and does not replace the outside-writer requirement. tmpfs and protected
system/root mount destinations are rejected, as are special archive entries,
unsafe archive paths, or snapshot warnings. A backup located inside a frontend
bind source is rejected to avoid recursive capture. No original mount is attached
to any recovery probe.

After unpausing the original, conservative backup-disk and Docker filesystem
space checks precede recovery. These are estimates, not reservations or guarantees
against concurrent disk consumption. Files are imported into a new private image;
mount contents are restored only into a new, unmounted, isolated bootstrap.
The bootstrap's copied paths may be removed to replace them with the captured
mount view. This never removes or changes source-container paths or original
mounted storage. Captured versus restored mounted data is compared for names,
content hashes, file types, ownership, permissions, and link targets.

The original environment, entrypoint, command, user and working directory are
replayed through a private JSON Compose file. Dollar signs are escaped for
Compose interpolation so `${...}` and `$literal` credentials remain literal.
Environment values and captured command arguments are never put in shell or
Docker CLI arguments. Docker CLI archive warnings fail capture rather than
quietly accepting potentially incomplete data. Duplicate environment keys are rejected.

A stopped container with this runtime configuration is committed to a final
private recovery image. A **new container using that image's defaults**, without
entrypoint/command overrides, must serve HTML at `/` and reject anonymous
`POST /api/documents/process` with 401. The probe has no network, published ports,
original mounts, privileges, or extra capabilities; it has CPU/memory limits and
`no-new-privileges`. Isolation and runtime configuration are inspected before
starting. Only helper-created probe/bootstrap containers are removed afterward.
Original containers, images, tags, volumes and mount sources are never deleted.

The recovery is a captured filesystem/runtime state, **not** the original missing
image ID, original build provenance, process memory, existing TCP sessions, or a
full host configuration. Original network names, ports, logging drivers and
host privileges are recorded privately but deliberately not replayed in probes.
The rootfs and mount archives plus metadata/manifest can independently reconstruct
and reverify the image using `verify-frontend-recovery --backup <private-child>`,
without the original container/image. A copy of the corrected helper is retained
in the private child for that purpose; local private images are retained too. Artifact hashes
check accidental corruption, not authenticity against a writer who can replace
both artifacts and manifest.

`prepare` now checkpoints each successful tag immediately. Only an explicit
missing-image result for the frontend ID activates capture; daemon errors and
tag failures stop instead. A missing backend image still requires a separate
plan. It never queries or substitutes `latest`. Cold Qdrant backup, service stops,
and source application proceed only after frontend recovery verification succeeds.

## Credentials and private artifacts

Treat **all** capture material as credential-bearing:

- Full inspect metadata includes environment, commands, labels, host mount paths,
  and potentially logging-driver or other host configuration secrets.
- Rootfs archives may include `.env`, private keys, caches and tokens; mount
  archives can contain external secrets or data absent from the image.
- Private Compose replay files and captured application/CLI logs can contain
  plaintext credentials. They are never printed as progress or exception details.
- Imported/intermediate/final Docker images can contain credential files; the
  final image also retains the runtime environment and command configuration.

The owned backup directory must be outside the checkout with mode 0700; capture
subdirectories are 0700 and every new capture file is exclusive-created at 0600.
No tar archive is extracted onto the host. Snapshots stream to disk rather than
being buffered whole in memory. Raw stdout/stderr and probe logs stay private;
public progress reports only generic success or failure. No artifact is uploaded,
pushed to a registry, added to Git, or printed in the review bundle. Docker images
are accessible to Docker administrators and local artifacts are **not encrypted**;
POSIX permissions do not certify host ACLs, disk encryption, or OS backup/sync
policy. The owner must keep the destination private under those policies too.

Do not send the Mac backup or its raw metadata/logs to Reviewer Codex. Review the
helper source and synthetic evidence; share only explicitly redacted diagnostics.
No automatic credential rotation or deletion is introduced. Do not prune the
running container, recovery images, successful backend tag, or old backup.

## Validation and limits

Commands in the cloud test environment:

```sh
python tests/test_mac_safe_update.py
python tests/test_mac_frontend_recovery.py
python tests/mac_frontend_recovery_smoke.py
```

The Docker smoke uses a digest-pinned Node 20 Alpine fixture, synthetic credentials,
a post-start writable-layer change, a read-only bind-mounted credential, and a
named-volume credential with owner 1000 and mode 0600. Its HTTP contract requires
those exact bytes, a literal dollar-containing environment value, and a captured
command argument containing dollars. It verifies
default recovery-image startup/auth, mounted data/ownership, no progress-output
credential leak, private file permissions, and the source still running/unpaused.
A second reconstruction runs the retained helper CLI after the disposable source
container and its image have been removed, proving independence from both.
Only the smoke test retires those fixtures; the actual helper never removes the
original source container or image. All test mount sources and images are disposable;
cleanup is confined to fixtures created by that smoke run.

This Linux Docker engine refuses deletion of an image used by a running fixture.
Therefore the exact missing-image Docker Desktop corruption is **not reproduced**.
Unavailable-image selection/checkpointing is simulated in unit tests; real Docker
export/import, independent artifact restoration, isolation and runtime verification
are exercised with the original image present but never used as a recovery parent.
These fixtures are a Node frontend contract, not the actual Mac Next image or a
fresh Next build. Mac/ARM capture, missing-image export behavior, real frontend
startup, authenticated login/gateway operation, browser recovery, and customer
PDF processing remain unverified. A failure at any of those gates must stop the
update rather than substitute the different image or bypass verification.

## After approval only

Use the newly reviewed helper, not the old helper retained in the backup. First
run its capture-only phase against the existing backup above; no mount-quiescence
flag is necessary if there are no mounts. If mounts are present, establish an
outside-writer quiescence plan before explicitly declaring it. Preserve the
resulting private child directory and require the isolated recovery `PASS` plus
confirmation that the original frontend remains running.

Do not treat this as permission to resume automatically. After capture passes,
agree the next preparation/rebuild step using a **fresh** backup destination.
The helper refuses to overwrite an existing preparation backup. The previous
Mac procedure's fresh-build, startup, synthetic upload and browser gates still
apply. No rollback to the old reader against newly published document revisions
is authorized by this recovery verification.


Evidence is in `validation/mac-frontend-recovery/`: nine preparation/helper
regressions, ten recovery/security regressions, and the two-case/four-startup
real-Docker artifact recovery smoke. All passed on the submitted source. The
original build attempt failed because the cloud default Buildx cache path was
read-only; the smoke now uses its own private writable Buildx directory. One
mounted run hit an order-sensitive Docker mount-list identity check; comparison
is now by destination, with a dedicated regression, and subsequent smoke passed.
These setup/test failures are retained separately from passing evidence.

No Mac backup contents, original credentials, container metadata, or captured
filesystem have been uploaded to this cloud workspace or committed. Every fixture
credential, label, file and volume in these tests is synthetic. The Mac's reported
unavailable image ID is an identifier, not a recovered artifact.
