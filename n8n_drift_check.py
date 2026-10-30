#!/usr/bin/env python3
"""Daily check for an n8n 2.x trap: the editor and direct SQL edits touch workflow_entity,
but a published workflow runs from workflow_history. When the two differ, what you see is not what runs.

Read only. Each run also plants a difference into a temporary table that disappears on ROLLBACK:
if the check does not see it, the check is blind, and that is reported as a failure, not as silence.

Exit codes: 0 fine, 1 workflows differ, 2 the check itself failed.
Settings (environment): N8N_PG_CONTAINER, N8N_PG_USER, N8N_PG_DB, DRIFT_STATE, DRIFT_ALERT_CMD.
DRIFT_ALERT_CMD is any shell command that reads the alert text from stdin. Without it the text is only printed."""
import json
import os
import subprocess
import sys
from pathlib import Path

CONTAINER = os.getenv("N8N_PG_CONTAINER", "n8n-postgres-1")
USER = os.getenv("N8N_PG_USER", "n8n")
DB = os.getenv("N8N_PG_DB", "n8n")
STATE = Path(os.getenv("DRIFT_STATE", "n8n-drift-state.json"))
ALERT_CMD = os.getenv("DRIFT_ALERT_CMD", "")

QUERY = """SELECT json_build_object('id', we.id, 'name', we.name, 'state',
  CASE WHEN wh."versionId" IS NULL THEN 'no-history'
       WHEN we.nodes::jsonb <> wh.nodes::jsonb OR we.connections::jsonb <> wh.connections::jsonb THEN 'drift'
       ELSE 'ok' END)
FROM {entity} we
LEFT JOIN workflow_history wh ON wh."workflowId" = we.id AND wh."versionId" = we."activeVersionId"
WHERE we.active ORDER BY we.name;"""
CANARY = f"""BEGIN;
CREATE TEMP TABLE drift_canary ON COMMIT DROP AS SELECT * FROM workflow_entity WHERE active;
UPDATE drift_canary SET nodes = '[]';
{QUERY.format(entity='drift_canary')}
ROLLBACK;"""


def psql(sql):
    c = subprocess.run(["docker", "exec", "-i", CONTAINER, "psql", "-U", USER, "-d", DB, "-Atq", "-v", "ON_ERROR_STOP=1"],
                       input=sql, capture_output=True, text=True, timeout=120)
    if c.returncode:
        raise RuntimeError(c.stderr.strip()[:200])
    return [json.loads(ln) for ln in c.stdout.splitlines() if ln.startswith("{")]


def decide(rows, canary, prev):
    """Returns (message or None, new state, exit code). No active workflows at all is a failure, not a quiet day."""
    if not rows:
        return "n8n-drift: the query returned no active workflows. The check is blind.", prev, 2
    if len(canary) != len(rows) or any(r["state"] == "ok" for r in canary):
        return "n8n-drift: the canary was not caught. Do not trust this check.", prev, 2
    bad = sorted(f"{r['name']} ({r['state']})" for r in rows if r["state"] != "ok")
    code = 1 if bad else 0
    if bad == prev:
        return None, prev, code
    if not bad:
        return f"n8n-drift: clear again, {len(rows)} active workflows match.", bad, 0
    return ("n8n runs something other than the editor shows (workflow_entity differs from the active workflow_history):\n" +
            "\n".join(bad)), bad, 1


def main():
    prev = json.loads(STATE.read_text()) if STATE.exists() else []
    try:
        rows, canary = psql(QUERY.format(entity="workflow_entity")), psql(CANARY)
        msg, state, code = decide(rows, canary, prev)
    except Exception as e:
        rows, msg, state, code = [], f"n8n-drift could not run: {type(e).__name__}: {str(e)[:160]}", prev, 2
    if msg:
        print(msg)
        if ALERT_CMD:
            subprocess.run(ALERT_CMD, shell=True, input=msg, text=True, timeout=60, check=True)
    else:
        print(f"quiet: {len(rows)} active, {len(state)} differ")
    STATE.write_text(json.dumps(state, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
