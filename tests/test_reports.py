import os
import sys
import re
import json
import math
import yaml
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from app.main import app
SANDBOX_REGEX = re.compile(r"^sbx-[a-z0-9]{8,}$")
ALLOWED_CAPABILITIES = {
    "persistence", "snapshots", "celestofs", "browser", "published_ports",
    "network_policy", "safety_hooks", "host_mounts", "coding_agent_preset", "agentor_durable"
}
ALLOWED_ATTACKS = {"prompt_injection_exfil", "destructive_command", "suspicious_package"}
ALLOWED_POLICIES = {"resume", "rollback", "fresh"}


def test_docker_compose_and_dockerfile():
    """Requirement 1: docker-compose.yml and Dockerfile validation."""
    compose_path = os.path.join(REPO_ROOT, "docker-compose.yml")
    dockerfile_path = os.path.join(REPO_ROOT, "Dockerfile")

    assert os.path.exists(compose_path), "docker-compose.yml must exist at repository root"
    assert os.path.exists(dockerfile_path), "Dockerfile must exist at repository root"

    with open(compose_path, "r", encoding="utf-8") as f:
        compose = yaml.safe_load(f)

    services = compose.get("services", {})
    assert "api" in services, "api service must be defined in docker-compose.yml"
    assert "ledger" in services, "ledger service must be defined in docker-compose.yml"

    # Ledger assertions
    ledger = services["ledger"]
    volumes = [str(v) for v in ledger.get("volumes", [])]
    assert any("./seeds" in v and "/docker-entrypoint-initdb.d" in v for v in volumes), \
        "ledger must mount ./seeds to /docker-entrypoint-initdb.d"
    
    ledger_hc = ledger.get("healthcheck", {})
    assert "test" in ledger_hc and "pg_isready" in str(ledger_hc["test"]), "ledger healthcheck must use pg_isready"
    for field in ["interval", "timeout", "retries", "start_period"]:
        assert field in ledger_hc, f"ledger healthcheck must specify {field}"

    # API assertions
    api = services["api"]
    api_hc = api.get("healthcheck", {})
    assert "test" in api_hc and "http://localhost:8080/health" in str(api_hc["test"]), \
        "api healthcheck must request http://localhost:8080/health"
    for field in ["interval", "timeout", "retries", "start_period"]:
        assert field in api_hc, f"api healthcheck must specify {field}"

    depends = api.get("depends_on", {})
    assert "ledger" in depends, "api must depend on ledger"
    if isinstance(depends, dict):
        assert depends["ledger"].get("condition") == "service_healthy", "api must wait until ledger is healthy"


def test_env_example_and_no_live_env():
    """Requirement 2: .env.example with placeholders and absence of .env."""
    env_example_path = os.path.join(REPO_ROOT, ".env.example")
    env_live_path = os.path.join(REPO_ROOT, ".env")

    assert os.path.exists(env_example_path), ".env.example must exist at root"
    assert not os.path.exists(env_live_path), ".env must not be present in repository root"

    with open(env_example_path, "r", encoding="utf-8") as f:
        content = f.read()

    required_keys = [
        "CELESTO_PROVIDER",
        "CELESTO_API_KEY",
        "LLM_API_KEY",
        "LLM_MODEL",
        "DATABASE_URL",
        "API_PORT"
    ]
    for key in required_keys:
        assert re.search(rf"^{key}=", content, re.MULTILINE), f".env.example must contain key {key}"

    # Confirm values are placeholders
    assert "replace-me" in content or "placeholder" in content or "example" in content


def test_problem_json():
    """Requirement 3: reports/problem.json schema and length constraints."""
    path = os.path.join(REPO_ROOT, "reports", "problem.json")
    assert os.path.exists(path), f"{path} must exist"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for field in ["who", "agent_work", "proof_output", "idea_source"]:
        assert field in data, f"problem.json missing {field}"

    assert len(data["who"]) >= 40, "who must be at least 40 characters"
    assert len(data["agent_work"]) >= 40, "agent_work must be at least 40 characters"
    assert len(data["proof_output"]) >= 20, "proof_output must be at least 20 characters"
    assert data["idea_source"] in {"idea_bank", "original"}, "idea_source must be idea_bank or original"


def test_commands_jsonl():
    """Requirement 4: logs/commands.jsonl audit format and celesto_sandbox target."""
    path = os.path.join(REPO_ROOT, "logs", "commands.jsonl")
    assert os.path.exists(path), f"{path} must exist"

    with open(path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    assert len(lines) >= 1, "logs/commands.jsonl must have at least one line"

    has_blocked = False
    for line in lines:
        obj = json.loads(line)
        assert "ts" in obj and obj["ts"], "line must contain ts"
        datetime.fromisoformat(obj["ts"].replace("Z", "+00:00"))  # Validate ISO format

        assert SANDBOX_REGEX.match(obj["sandbox_name"]), f"Invalid sandbox_name {obj['sandbox_name']}"
        assert obj["command"], "command must be non-empty"
        assert obj["decision"] in {"allow", "block"}, f"Invalid decision {obj['decision']}"
        assert obj["execution_target"] == "celesto_sandbox", "execution_target must be exactly celesto_sandbox"

        if obj["decision"] == "block":
            has_blocked = True

    assert has_blocked, "Audit log should include blocked command from containment test"


def test_capabilities_json():
    """Requirement 5: reports/capabilities.json differentiating capabilities and evidence."""
    path = os.path.join(REPO_ROOT, "reports", "capabilities.json")
    assert os.path.exists(path), f"{path} must exist"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    caps = data.get("capabilities", [])
    assert len(caps) >= 2, "capabilities must have at least two objects"

    ids = [c["id"] for c in caps]
    assert len(ids) == len(set(ids)), "capability ids must be unique"

    for cap in caps:
        assert cap["id"] in ALLOWED_CAPABILITIES, f"Invalid capability id {cap['id']}"
        assert len(cap["why"]) >= 80, f"why for {cap['id']} must be at least 80 chars"
        ev_path = os.path.join(REPO_ROOT, cap["evidence_path"])
        assert os.path.exists(ev_path), f"evidence_path {cap['evidence_path']} must exist in repo"


def test_lifecycle_json():
    """Requirement 6: reports/lifecycle.json cleanup flags and sandbox names."""
    path = os.path.join(REPO_ROOT, "reports", "lifecycle.json")
    assert os.path.exists(path), f"{path} must exist"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("cleanup_on_success") is True
    assert data.get("cleanup_on_failure") is True
    assert data.get("cleanup_on_interrupt") is True

    names = data.get("sandbox_names", [])
    assert len(names) >= 1, "sandbox_names must be non-empty"
    assert len(names) == len(set(names)), "sandbox_names must be unique"

    # Read commands and reliability to verify presence
    cmd_path = os.path.join(REPO_ROOT, "logs", "commands.jsonl")
    rel_path = os.path.join(REPO_ROOT, "reports", "reliability.json")

    cmd_names = set()
    if os.path.exists(cmd_path):
        with open(cmd_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    cmd_names.add(json.loads(line).get("sandbox_name"))

    rel_names = set()
    if os.path.exists(rel_path):
        with open(rel_path, "r", encoding="utf-8") as f:
            for r in json.load(f).get("runs", []):
                rel_names.add(r.get("sandbox_name"))

    for name in names:
        assert SANDBOX_REGEX.match(name), f"Sandbox name {name} does not match pattern"
        assert name in cmd_names or name in rel_names, f"Sandbox {name} must appear in commands or reliability"


def test_reliability_json_and_postmortem():
    """Requirement 7: reports/reliability.json arithmetic and reports/postmortem.md."""
    path = os.path.join(REPO_ROOT, "reports", "reliability.json")
    assert os.path.exists(path), f"{path} must exist"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    runs = data.get("runs", [])
    run_count = data.get("run_count")

    assert len(runs) >= 20, "Must have at least 20 runs"
    assert run_count == len(runs), "run_count must equal len(runs)"

    names = [r["sandbox_name"] for r in runs]
    assert len(names) == len(set(names)), "sandbox_names in runs must be unique"

    for r in runs:
        assert SANDBOX_REGEX.match(r["sandbox_name"])
        assert r["fresh"] is True
        assert isinstance(r["success"], bool)
        assert r["wall_clock_s"] >= 0
        assert r["boot_to_ready_s"] >= 0
        assert r["cost_usd"] >= 0

    # Arithmetic check
    n = len(runs)
    expected_rate = sum(1 for r in runs if r["success"]) / n
    assert abs(data["success_rate"] - expected_rate) <= 0.001

    sorted_wc = sorted(r["wall_clock_s"] for r in runs)
    expected_median_wc = (sorted_wc[9] + sorted_wc[10]) / 2.0
    assert abs(data["median_wall_clock_s"] - expected_median_wc) <= 0.001

    p90_idx = int(math.ceil(0.90 * n)) - 1
    expected_p90_wc = sorted_wc[p90_idx]
    assert abs(data["p90_wall_clock_s"] - expected_p90_wc) <= 0.001

    sorted_boot = sorted(r["boot_to_ready_s"] for r in runs)
    expected_median_boot = (sorted_boot[9] + sorted_boot[10]) / 2.0
    assert abs(data["median_boot_to_ready_s"] - expected_median_boot) <= 0.001

    expected_cost = sum(r["cost_usd"] for r in runs)
    assert abs(data["total_cost_usd"] - expected_cost) <= 0.01

    pm_path = os.path.join(REPO_ROOT, data["postmortem_path"])
    assert os.path.exists(pm_path), "postmortem_path must exist"
    with open(pm_path, "r", encoding="utf-8") as f:
        pm_content = f.read()
    assert len(pm_content) >= 200, "postmortem.md must be at least 200 characters"


def test_containment_json():
    """Requirement 8: reports/containment.json defense and untouched host."""
    path = os.path.join(REPO_ROOT, "reports", "containment.json")
    assert os.path.exists(path), f"{path} must exist"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["attack"] in ALLOWED_ATTACKS
    assert data["blocked"] is True
    assert data["host_untouched"] is True

    evidence_paths = data.get("evidence_paths", [])
    assert len(evidence_paths) >= 1
    for ep in evidence_paths:
        full_ep = os.path.join(REPO_ROOT, ep)
        assert os.path.exists(full_ep), f"evidence file {ep} must exist"


def test_failure_policy_json_and_trace():
    """Requirement 9: reports/failure_policy.json and failure_trace.jsonl."""
    policy_path = os.path.join(REPO_ROOT, "reports", "failure_policy.json")
    assert os.path.exists(policy_path), f"{policy_path} must exist"

    with open(policy_path, "r", encoding="utf-8") as f:
        policy_data = json.load(f)

    assert policy_data["failed_step"] == 7
    assert policy_data["total_steps"] == 10
    assert policy_data["policy"] in ALLOWED_POLICIES
    assert len(policy_data["rationale"]) >= 200

    trace_path = os.path.join(REPO_ROOT, policy_data["trace_path"])
    assert os.path.exists(trace_path), "trace_path must exist"

    with open(trace_path, "r", encoding="utf-8") as f:
        trace_lines = [json.loads(line) for line in f if line.strip()]

    found_policy_applied = False
    for step_obj in trace_lines:
        if step_obj.get("event") == "policy_applied":
            assert step_obj.get("policy") == policy_data["policy"]
            found_policy_applied = True

    assert found_policy_applied, "trace must contain an event equal to policy_applied matching policy"


def test_concurrency_json():
    """Requirement 10: reports/concurrency.json >= 5 jobs and breakage notes."""
    path = os.path.join(REPO_ROOT, "reports", "concurrency.json")
    assert os.path.exists(path), f"{path} must exist"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    jobs = data.get("jobs", [])
    assert len(jobs) >= 5, "jobs must have at least five objects"

    names = [j["sandbox_name"] for j in jobs]
    assert len(names) == len(set(names)), "concurrency sandbox names must be unique"

    for j in jobs:
        assert SANDBOX_REGEX.match(j["sandbox_name"])
        assert j.get("started_at"), "started_at must be non-empty"

    assert len(data.get("breakage_notes", "")) >= 40, "breakage_notes must be at least 40 characters"


def test_readme_phrases():
    """Requirement 12: README.md required phrases."""
    readme_path = os.path.join(REPO_ROOT, "README.md")
    assert os.path.exists(readme_path), "README.md must exist at repository root"

    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    required_phrases = [
        "Problem statement",
        "How I used Celesto",
        "Eval report",
        "Containment test",
        "State and failure design",
        "Setup"
    ]
    for phrase in required_phrases:
        assert phrase in content, f"README.md must contain phrase '{phrase}'"


def test_api_endpoints():
    """Requirement 11: Ledger API health, listing runs, and run creation validation."""
    client = TestClient(app)

    # 1. GET /health
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json() == {"status": "ok"}

    # 2. GET /api/runs (includes seeded sbx-seeddemo1)
    res_runs = client.get("/api/runs")
    assert res_runs.status_code == 200
    runs = res_runs.json()
    assert isinstance(runs, list)
    assert any(r.get("sandbox_name") == "sbx-seeddemo1" for r in runs), \
        "sbx-seeddemo1 must be present in runs"

    # 2b. Control plane serves produced report files
    res_report = client.get("/reports/problem.json")
    assert res_report.status_code == 200


    # 3. POST /api/runs valid payload
    valid_payload = {
        "run_id": "run-test001",
        "sandbox_name": "sbx-testapi01",
        "problem_id": "job-hunt-research",
        "state": "succeeded",
        "execution_target": "celesto_sandbox"
    }
    res_post = client.post("/api/runs", json=valid_payload)
    assert res_post.status_code == 201
    created = res_post.json()
    assert created["sandbox_name"] == "sbx-testapi01"
    assert created["execution_target"] == "celesto_sandbox"

    # 4. POST /api/runs invalid execution_target -> 400
    invalid_target = {
        "run_id": "run-test002",
        "sandbox_name": "sbx-testapi02",
        "problem_id": "job-hunt-research",
        "state": "succeeded",
        "execution_target": "host"
    }
    res_bad_target = client.post("/api/runs", json=invalid_target)
    assert res_bad_target.status_code == 400

    # 5. POST /api/runs unknown state -> 400
    invalid_state = {
        "run_id": "run-test003",
        "sandbox_name": "sbx-testapi03",
        "problem_id": "job-hunt-research",
        "state": "unknown_state",
        "execution_target": "celesto_sandbox"
    }
    res_bad_state = client.post("/api/runs", json=invalid_state)
    assert res_bad_state.status_code == 400

    # 6. POST /api/runs bad sandbox_name -> 400
    invalid_name = {
        "run_id": "run-test004",
        "sandbox_name": "bad-name",
        "problem_id": "job-hunt-research",
        "state": "created",
        "execution_target": "celesto_sandbox"
    }
    res_bad_name = client.post("/api/runs", json=invalid_name)
    assert res_bad_name.status_code == 400
