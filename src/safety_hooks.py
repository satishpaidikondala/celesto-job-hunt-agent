import os
import re
import json
from datetime import datetime, timezone

COMMAND_LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "commands.jsonl")

# Patterns blocked by safety hooks
BLOCKED_PATTERNS = [
    re.compile(r"rm\s+-rf\s+(/|~|\$HOME)", re.IGNORECASE),
    re.compile(r"curl\s+.*(attacker\.com|exfil|webhook)", re.IGNORECASE),
    re.compile(r"(cat|head|tail|grep)\s+.*(/etc/shadow|id_rsa)", re.IGNORECASE),
    re.compile(r":\(\)\s*\{\s*:\|:&\s*\};:", re.IGNORECASE),  # fork bomb
    re.compile(r"pip\s+install\s+.*(malicious-stealer|typo-squat)", re.IGNORECASE),
]


class CommandBlockedError(Exception):
    """Raised when a command is blocked by a safety hook before reaching the microVM."""
    pass


def audit_command(sandbox_name: str, command: str, decision: str) -> dict:
    """
    Append command attempt to logs/commands.jsonl.
    Enforces execution_target = celesto_sandbox and ISO-8601 timestamps.
    """
    os.makedirs(os.path.dirname(COMMAND_LOG_PATH), exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "sandbox_name": sandbox_name,
        "command": command.strip(),
        "decision": decision,
        "execution_target": "celesto_sandbox"
    }
    with open(COMMAND_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def pre_exec_hook(sandbox_name: str, command: str) -> None:
    """
    Inspect command before sending to the Celesto microVM.
    Blocks forbidden/destructive actions before the guest sees them.
    """
    for pattern in BLOCKED_PATTERNS:
        if pattern.search(command):
            audit_command(sandbox_name, command, "block")
            raise CommandBlockedError(f"Command blocked by safety hook: '{command}' matched policy pattern.")
    
    audit_command(sandbox_name, command, "allow")
