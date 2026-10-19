# External staging release runbook

This runbook deploys an immutable HAHA staging release behind an HTTPS ingress. It does not authorize
a Production Candidate or production deployment.

## Required inputs

- A full Git commit SHA whose HAHA CI run is green and whose value is stored as `HAHA_GIT_SHA`.
- API and Web images built from that same commit, scanned, pushed and recorded by `@sha256` digest.
- PostgreSQL and Redis images recorded by digest.
- A private environment file based on `config/release.env.example`.
- Named release, rollback, security, data and on-call owners.
- A current PostgreSQL backup, a synchronized community-media backup and enough free space for both
  restore drills.

The Web image must be built with `NEXT_PUBLIC_API_BASE_URL` equal to `HAHA_PUBLIC_API_URL` and
`NEXT_PUBLIC_AUTH_MODE=jwt`. Do not put JWT or database secrets in image build arguments.
The image records both non-secret values in `io.haha.web.api-base-url` and
`io.haha.web.auth-mode` labels so the release owner can verify the immutable artifact.

## Preflight

```powershell
$releaseEnv = "C:\secure\haha-staging.env"
python scripts/release_preflight.py --env-file $releaseEnv
docker compose --env-file $releaseEnv -f compose.release.yaml config --quiet
docker compose --env-file $releaseEnv -f compose.release.yaml pull
$releaseValues = @{}
Get-Content $releaseEnv | Where-Object { $_ -match '^[^#][^=]*=' } | ForEach-Object {
  $key, $value = $_.Split('=', 2); $releaseValues[$key.Trim()] = $value.Trim()
}
$webImage = $releaseValues['HAHA_WEB_IMAGE']
$apiImage = $releaseValues['HAHA_API_IMAGE']
$webApi = docker image inspect $webImage --format '{{ index .Config.Labels "io.haha.web.api-base-url" }}'
$webAuth = docker image inspect $webImage --format '{{ index .Config.Labels "io.haha.web.auth-mode" }}'
$webRevision = docker image inspect $webImage --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}'
$apiRevision = docker image inspect $apiImage --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}'
if ($webApi -ne $releaseValues['HAHA_PUBLIC_API_URL'] -or $webAuth -ne 'jwt') { throw 'Web image API/auth labels do not match release configuration' }
if ($webRevision -ne $releaseValues['HAHA_GIT_SHA'] -or $apiRevision -ne $releaseValues['HAHA_GIT_SHA']) { throw 'Image revisions do not match HAHA_GIT_SHA' }
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
3. Create a custom-format PostgreSQL backup and synchronized media backup before applying migrations.
4. Run the one-shot `migrate` service and record its exit code and resulting Alembic revision.
5. Start API and Worker; require API `/ready` and Worker health to pass.
6. Start Web and enable the ingress route only after API readiness.
7. Issue a short-lived staging owner token through the private bootstrap/identity path.
8. Run `scripts/release_smoke.py` using the public HTTPS URLs.
9. Run the PostgreSQL and media restore drills; any metadata/file mismatch blocks the release.
10. Run the C4 browser generation, cancellation and failed-job scenarios when the release changes any
   API, Worker or Web behavior.
11. Observe errors, latency, queue depth and failed jobs for at least 15 minutes before sign-off.

Example smoke invocation (token remains an environment value and is not printed):

```powershell
$env:HAHA_PUBLIC_API_URL = "https://api.staging.example.com"
$env:HAHA_PUBLIC_WEB_ORIGIN = "https://staging.example.com"
$env:HAHA_RELEASE_ID = "the-approved-release-id"
$env:HAHA_GIT_SHA = "the-full-40-character-commit-sha"
$env:HAHA_RELEASE_ACCESS_TOKEN = "short-lived-token"
$env:HAHA_METRICS_TOKEN = "separate-32-plus-character-monitoring-token"
python scripts/release_smoke.py
```

The metrics token must be delivered to the private metrics collector and must not equal the JWT
signing secret. The smoke gate verifies that anonymous metrics access is rejected.

## Acceptance record

Record the release ID, Git SHA, four image digests, migration revision, database/media backup
identifiers, smoke result, browser evidence, start/end time and all five owner acknowledgements. A
missing record keeps the release gate open.

## Rollback rehearsal

1. Record the currently running digests and database/media recovery point before changing anything.
2. Repoint API, Worker and Web to the previously approved immutable digests; never use a mutable tag.
3. If the previous application is schema-compatible, restart in dependency order and rerun smoke plus
   the critical browser path.
4. If schema is incompatible, restore PostgreSQL into a new database and media into a new object prefix
   from the same recovery point, verify both manifests, then switch connection/routing configuration.
5. Do not restore over the source database or live media prefix. A failed rehearsal blocks sign-off.

The 2026-10-19 local rehearsal proved isolated deployment, smoke and both restore scripts. It did not
exercise a real ingress, off-host recovery point or externally routed rollback, so external rollback
remains `BLOCKED`.
