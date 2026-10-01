# HAHA staging runbook

Staging uses JWT authentication and real PostgreSQL, Redis and Dramatiq services. It must never use
`HAHA_AUTH_MODE=dev`.

1. Copy `config/staging.env.example` to an ignored local environment file and replace both secrets.
2. Load those variables into the shell.
3. Run `docker compose -f compose.staging.yaml up -d --build`.
4. Create the initial staging operator and a one-hour token:

   `docker compose -f compose.staging.yaml --profile tools run --rm bootstrap python -m haha_api.staging_bootstrap --show-token`

5. Open `http://127.0.0.1:13000` and paste that short-lived token into the staging token field.
6. Inspect API readiness at `http://127.0.0.1:18000/ready` and metrics at
   `http://127.0.0.1:18000/metrics`.

The bootstrap issuer is for private staging verification only. A real deployment must replace it with
the organization identity provider, short-lived access tokens and managed secret storage.
