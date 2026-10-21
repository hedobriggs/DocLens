# Start here

Use the working `package/portable-docker` branch in a separate folder. Docker
Desktop/Engine must be running; Python 3 and Docker Compose 2.30+ are required.
Images target Linux amd64; physical Mac and Apple Silicon acceptance remain
unverified here. Keep your original installation and data untouched.

## One-time private provider key

From the repository root:

```sh
cp .env.example .env
chmod 600 .env
```

Edit `.env` privately, replacing the placeholder with your Gemini API key.
Alternatively supply `GEMINI_API_KEY` through your server's secret environment.
Never commit a real key or paste it in chat. No shell expressions in `.env` are
executed. Existing configured portable installations can skip this step: their
private `.runtime` already contains the saved key.

## Start and stop

```sh
./start
```

First setup builds missing images and asks for email, password (12+ characters,
at most 72 UTF-8 bytes) and password confirmation. Save the password securely.
Later starts reuse settings and do not prompt. Open the printed address, normally
http://127.0.0.1:3000. For a fresh installation alongside an existing one, use
`./start --port 3001`. An existing saved port is never silently changed.

```sh
./stop
```

This stops only this checkout's project. Named volumes and settings remain.
It does not delete containers, images or documents. Avoid `down -v` and volume
prune on any deployment with data you want to retain.

The scripts preserve any existing portable `.runtime`, including its original
image tags. They do not reset forgotten passwords, upgrade an installation's
images, or migrate another project's data. Newly configured projects use the
current `3a07c4d` image tags. Older `66db29f` image archives remain historical.

For public-server DNS/HTTPS, manual configuration, backups and synthetic tests,
see [README.md](README.md). The simple launcher binds to loopback and does not
configure cloud firewalls or public TLS. Upload limits remain 32 MiB / 300 pages.
Read [VALIDATION.md](VALIDATION.md) for evidence and platform limitations.
