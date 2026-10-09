# External staging release runbook

This runbook deploys an immutable HAHA staging release behind an HTTPS ingress. It does not authorize
a Production Candidate or production deployment.

## Required inputs

- A Git commit whose HAHA CI run is green.
- API and Web images built from that same commit, scanned, pushed and recorded by `@sha256` digest.
- PostgreSQL and Redis images recorded by digest.
- A private environment file based on `config/release.env.example`.
- Named release, rollback, security, data and on-call owners.
- A current PostgreSQL backup and enough free space for a restore drill.

The Web image must be built with `NEXT_PUBLIC_API_BASE_URL` equal to `HAHA_PUBLIC_API_URL` and
`NEXT_PUBLIC_AUTH_MODE=jwt`. Do not put JWT or database secrets in image build arguments.

## Preflight

```powershell
$releaseEnv = "C:\secure\haha-staging.env"
python scripts/release_preflight.py --env-file $releaseEnv
docker compose --env-file $releaseEnv -f compose.release.yaml config --quiet
docker compose --env-file $releaseEnv -f compose.release.yaml pull
```

Stop if the preflight reports a placeholder, mutable image tag, non-HTTPS origin, wildcard CORS,
public container bind or missing owner. Store the populated environment file in the deployment host's
secret manager or protected filesystem, never in Git.

`--allow-loopback` and `--allow-local-image-ids` exist only for an isolated release rehearsal where
no registry or public ingress is involved. They are forbidden for an external staging deployment.

## Controlled deployment

1. Record the current environment file, image digests, Git SHA, Alembic revision and latest verified
   backup identifier in the change ticket.
2. Start only PostgreSQL and Redis, then confirm both health checks.
3. Create a custom-format PostgreSQL backup before applying migrations.
4. Run the one-shot `migrate` service and record its exit code and resulting Alembic revision.
5. Start API and Worker; require API `/ready` and Worker health to pass.
6. Start Web and enable the ingress route only after API readiness.
7. Issue a short-lived staging owner token through the private bootstrap/identity path.
8. Run `scripts/release_smoke.py` using the public HTTPS URLs.
9. Run the C4 browser generation, cancellation and failed-job scenarios when the release changes any
   API, Worker or Web behavior.
10. Observe errors, latency, queue depth and failed jobs for at least 15 minutes before sign-off.

Example smoke invocation (token remains an environment value and is not printed):

```powershell
$env:HAHA_PUBLIC_API_URL = "https://api.staging.example.com"
$env:HAHA_PUBLIC_WEB_ORIGIN = "https://staging.example.com"
$env:HAHA_RELEASE_ID = "the-approved-release-id"
$env:HAHA_RELEASE_ACCESS_TOKEN = "short-lived-token"
python scripts/release_smoke.py
```

## Acceptance record

Record the release ID, Git SHA, four image digests, migration revision, backup identifier, smoke result,
browser evidence, start/end time and all five owner acknowledgements. A missing record keeps the
release gate open.
