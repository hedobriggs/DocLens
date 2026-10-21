# Start here

For a Git clone, the simplest local setup is now documented in the
[root README](../../README.md): provide a private Gemini key once, then use
`./start` and `./stop`. First startup prompts for email/password/confirmation;
later starts reuse your saved settings. The archive/manual procedure follows.

This package runs the same approved application source as the RunPod trial:
`66db29f0b072fd9821869f4ffef008883ce0509b`. It does not contain your RunPod
credentials or documents and does not update your Mac.

Use a **new Docker-capable Linux amd64 server**, or a separate trial directory
on Intel Mac Docker Desktop. Docker Compose 2.30+ and Python 3 are needed. The
current native RunPod container has no Docker daemon; do not run these Compose
commands there. See README.md for supported hosts and resource planning.

1. Download and verify the release files against `SHA256SUMS`. On Linux use
   `sha256sum -c SHA256SUMS`; on macOS use `shasum -a 256 -c SHA256SUMS`.
2. Unzip `DocLens-portable-source.zip` into a NEW folder. Keep the image archive
   nearby; record its full path. Never extract over the existing Mac checkout.
3. Load the two custom images (replace the path with your download location):

   ```sh
   gzip -dc /absolute/path/DocLens-portable-linux-amd64-images.tar.gz | docker image load
   ```

   Check both images appear in `docker image ls`. Alternatively, build from
   source using `python3 deploy/portable/build.py` in the unpacked repository.
4. In `DocLens-portable/deploy/portable`, pull Qdrant and perform a synthetic test:

   ```sh
   docker pull qdrant/qdrant:v1.15.5@sha256:0fb8897412abc81d1c0430a899b9a81eb8328aa634e7242d1bc804c1fe8fe863
   python3 configure.py --synthetic-test --port 0
   ./doclens up -d --no-build --wait --wait-timeout 180
   python3 smoke.py --restart
   ```

   Run each command only after the previous command succeeds. This uses a dummy
   Gemini key and tests actual PDF ingestion/storage without provider calls.
   Preserve the output. It is an automated test, not a ready-to-use public app.
5. For a real deployment, use ANOTHER fresh package directory/project; do not
   overwrite the synthetic runtime files. Configure with:

   ```sh
   python3 configure.py --domain YOUR-REAL-DNS-HOSTNAME
   ./doclens --https up -d --no-build --wait --wait-timeout 180
   ```

   Replace the hostname; point its DNS to the server first and allow inbound
   TCP 80/443. The initializer prompts privately for login details and Gemini
   key. Open `https://YOUR-REAL-DNS-HOSTNAME` after Caddy has obtained a valid
   certificate. Do not expose backend 8000 or database 6333/6334.

Keep the persistent Docker volumes and `.runtime` files private. Never run
`down -v` or volume prune on a deployment containing data you want to retain.
Back up and test restore before relying on the service. README.md contains
backup, restart, proxy trust and troubleshooting details; VALIDATION.md records
exact test scope, initial failures and unverified platforms.

Images have been built and exported, not published to a registry. Deployment to
a real server, native Mac acceptance and migration of existing data are separate
steps. Current upload limits remain 32 MiB / 300 pages; this package does not
make a 2,786-page PDF acceptable as one upload.
