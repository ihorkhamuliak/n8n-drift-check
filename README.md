# n8n-drift-check

**English** · [Українська](README.uk.md)

A daily check for one trap in n8n 2.x: **what you see in the editor is not always what runs.**

The editor and any direct SQL edit touch `workflow_entity`. A published workflow runs from `workflow_history`,
the version that `activeVersionId` points to. When the two differ, nothing fails and nothing warns you.

It cost me twice. Once a language change was live in the database and in every check I ran, while the old workflow kept posting for days.
Another time a fix sat in `workflow_entity` for a day and never ran.

## What it does

For every active workflow it compares `nodes` and `connections` between the two tables, as JSON, so formatting does not matter.

| Exit code | Meaning |
|---|---|
| `0` | all match |
| `1` | at least one workflow differs |
| `2` | the check itself failed |

A given set of differences is reported once. A new set is reported at once, and so is the moment it clears.

## Why it can be trusted

A check that only ever stays quiet proves nothing. On every run it copies the active workflows into a temporary table,
plants a difference into all of them and runs the same query. If any of them is missed, it reports that it is blind.
The table disappears on `ROLLBACK`, and the real tables are only read.

## Setup

Python 3 and `docker` on the host of a self-hosted n8n with Postgres. No dependencies.

```bash
python3 n8n_drift_check.py
```

| Variable | Default | Meaning |
|---|---|---|
| `N8N_PG_CONTAINER` | `n8n-postgres-1` | Postgres container |
| `N8N_PG_USER` | `n8n` | database user |
| `N8N_PG_DB` | `n8n` | database name |
| `DRIFT_STATE` | `n8n-drift-state.json` | remembers what was already reported |
| `DRIFT_ALERT_CMD` | empty | any shell command that reads the alert from stdin, for example a Telegram sender |

Daily cron:

```cron
30 7 * * * cd ~/n8n-drift && DRIFT_ALERT_CMD='/usr/local/bin/notify' python3 n8n_drift_check.py >> drift.log 2>&1
```

## Limits

- A difference is not always a bug: an unpublished draft in the editor also shows up. Look at what differs before you act.
- Nothing watches the cron itself. If it stops, you get no signal.
- The table and column names come from n8n 2.25 and 2.41. A later version may rename them, and then the check exits with `2`.

## Tests

```bash
python test_n8n_drift_check.py
```

## License

MIT
