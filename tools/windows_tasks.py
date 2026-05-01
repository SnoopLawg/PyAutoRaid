"""Windows Task Scheduler CRUD scoped to \\PyAutoRaid\\.

Extracted from dashboard_server.py for separation of concerns. Each
function returns (ok: bool, message: str) and shells out via schtasks
or PowerShell Get-ScheduledTask. All names are validated against
TASK_NAME_RE before any subprocess invocation to prevent injection.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess

logger = logging.getLogger(__name__)

TASK_FOLDER = r"\PyAutoRaid"
TASK_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}$")


def _run_cmd(args: list[str], timeout: int = 20) -> tuple[int, str, str]:
    """Run a command list and return (returncode, stdout, stderr)."""
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except FileNotFoundError as e:
        return 127, "", str(e)


def list_scheduled_tasks() -> list[dict]:
    r"""Return list of dicts for every task under \PyAutoRaid\."""
    ps = r"""
$out = @()
foreach ($t in (Get-ScheduledTask -TaskPath '\PyAutoRaid\*' -ErrorAction SilentlyContinue)) {
    $info = $t | Get-ScheduledTaskInfo
    $a = if ($t.Actions.Count -gt 0) { $t.Actions[0] } else { $null }
    $tr = if ($t.Triggers.Count -gt 0) { $t.Triggers[0] } else { $null }
    $out += [PSCustomObject]@{
        name = $t.TaskName
        enabled = ($t.State -ne 'Disabled')
        state = $t.State.ToString()
        execute = if ($a) { $a.Execute } else { '' }
        arguments = if ($a) { $a.Arguments } else { '' }
        workingDir = if ($a) { $a.WorkingDirectory } else { '' }
        startBoundary = if ($tr) { [string]$tr.StartBoundary } else { '' }
        lastRun = [string]$info.LastRunTime
        nextRun = [string]$info.NextRunTime
        lastResult = $info.LastTaskResult
    }
}
if ($out.Count -eq 0) { Write-Output '[]' }
elseif ($out.Count -eq 1) { Write-Output ('[' + ($out[0] | ConvertTo-Json -Depth 3 -Compress) + ']') }
else { $out | ConvertTo-Json -Depth 3 -Compress }
""".strip()
    rc, out, err = _run_cmd([
        "powershell", "-NoProfile", "-NonInteractive", "-Command", ps
    ], timeout=15)
    if rc != 0:
        logger.info("list_scheduled_tasks rc=%s err=%s", rc, err[:200])
        return []
    if not out:
        return []
    try:
        data = json.loads(out)
        return data if isinstance(data, list) else [data]
    except json.JSONDecodeError as e:
        logger.info("list_scheduled_tasks parse err: %s", e)
        return []


def create_scheduled_task(name: str, time_hhmm: str, command: str) -> tuple[bool, str]:
    if not TASK_NAME_RE.match(name or ""):
        return False, "invalid name (A-Z, 0-9, underscore, dash only)"
    if not TIME_RE.match(time_hhmm or ""):
        return False, "time must be HH:MM"
    if not command or not command.strip():
        return False, "command required"
    tn = f"{TASK_FOLDER}\\{name}"
    rc, out, err = _run_cmd([
        "schtasks", "/Create", "/SC", "DAILY",
        "/TN", tn, "/TR", command, "/ST", time_hhmm, "/F"
    ])
    if rc == 0:
        return True, "created"
    return False, (err or out or f"exit {rc}")[:300]


def delete_scheduled_task(name: str) -> tuple[bool, str]:
    if not TASK_NAME_RE.match(name or ""):
        return False, "invalid name"
    tn = f"{TASK_FOLDER}\\{name}"
    rc, out, err = _run_cmd(["schtasks", "/Delete", "/TN", tn, "/F"])
    if rc == 0:
        return True, "deleted"
    return False, (err or out or f"exit {rc}")[:300]


def set_scheduled_task_enabled(name: str, enabled: bool) -> tuple[bool, str]:
    if not TASK_NAME_RE.match(name or ""):
        return False, "invalid name"
    tn = f"{TASK_FOLDER}\\{name}"
    flag = "/ENABLE" if enabled else "/DISABLE"
    rc, out, err = _run_cmd(["schtasks", "/Change", "/TN", tn, flag])
    if rc == 0:
        return True, "toggled"
    return False, (err or out or f"exit {rc}")[:300]
