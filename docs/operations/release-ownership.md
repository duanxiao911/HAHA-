# Release ownership and sign-off

Every external staging environment must map the following environment keys to named people or
accountable teams. `scripts/release_preflight.py` rejects empty and placeholder values.

| Responsibility | Environment key | Required decision |
|---|---|---|
| Release coordinator | `HAHA_RELEASE_OWNER` | Approves scope, commit, immutable digests and window |
| Rollback commander | `HAHA_ROLLBACK_OWNER` | Owns rollback decision, execution and RTO record |
| Security approver | `HAHA_SECURITY_OWNER` | Accepts no open release blockers and validates exposure |
| Data/backup owner | `HAHA_DATA_OWNER` | Confirms backup, migration and restore evidence |
| Incident contact | `HAHA_ONCALL_CONTACT` | Monitors the release and receives staging alerts |

One person may fill more than one role only when the deployment organization explicitly accepts that
risk. Security approval cannot waive the four deferred findings for a Production Candidate decision;
those findings must be fixed and retested.

The release record must include timestamped acknowledgements rather than only the values copied into
the environment file.
