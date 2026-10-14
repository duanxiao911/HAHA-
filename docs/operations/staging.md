# HAHA staging runbook

Staging uses JWT authentication and real PostgreSQL, Redis and Dramatiq services. It must never use
`HAHA_AUTH_MODE=dev`.

1. Copy `config/staging.env.example` to an ignored local environment file and replace both secrets.
2. Load those variables into the shell.
3. Run `docker compose -f compose.staging.yaml up -d --build`.
4. Create or rotate the initial internal staging operator credential:

   `docker compose -f compose.staging.yaml --profile tools run --rm bootstrap`

5. Terminate TLS in front of the staging Web service, then open `/login` and sign in with
   `staging-owner@haha.local`, workspace `staging`, and the password supplied through the ignored
   `HAHA_BOOTSTRAP_PASSWORD` environment value. Access and refresh tokens remain in HttpOnly cookies.
6. Inspect API readiness at `http://127.0.0.1:18000/ready` and metrics at
   `http://127.0.0.1:18000/metrics`.

The password bootstrap is for private staging verification only. Public registration remains disabled.
Before a public release, replace this internal account flow with the selected organization identity
provider and managed secret storage.
