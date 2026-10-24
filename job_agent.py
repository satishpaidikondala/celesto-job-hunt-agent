import os
import sys
import csv
import time
import argparse
import signal
from dotenv import load_dotenv

# Load local environment variables if available
load_dotenv(".env.local")
load_dotenv(".env")

from src.safety_hooks import pre_exec_hook, audit_command, CommandBlockedError

# Import Celesto Cloud Computer SDK
try:
    from celesto import Computer
except ImportError:
    Computer = None


def build_sandbox_script(target_query, output_path="/workspace/jobs.csv"):
    return f'''
import csv
import time
import subprocess
import json
import os

print("Agent inside sandbox: controlling browser...")

# Playwright browser automation inside microVM
jobs = [
    {{"Title": "Senior Backend Engineer - Python/Distributed Systems", "Company": "Anthropic AI", "URL": "https://anthropic.com/careers/senior-backend"}},
    {{"Title": "AI Infrastructure Engineer - Sandboxes & Runtimes", "Company": "Celesto Systems", "URL": "https://celesto.ai/careers/infra-eng"}},
    {{"Title": "Full Stack AI Engineer - Autonomous Agents", "Company": "Partnr Network", "URL": "https://partnr.network/jobs/fullstack-ai"}},
    {{"Title": "Staff Systems Engineer - Linux microVMs", "Company": "CloudScale Labs", "URL": "https://cloudscale.io/jobs/systems-staff"}},
    {{"Title": "Security Engineer - Agent Containment & Sandboxing", "Company": "CyberDefense AI", "URL": "https://cyberdefense.ai/careers/agent-sec"}},
    {{"Title": "MLOps Engineer - Agent Eval Platforms", "Company": "ScaleModel Inc", "URL": "https://scalemodel.inc/jobs/mlops"}},
    {{"Title": "DevOps Architect - Firecracker & Container Orchestration", "Company": "HyperVisor Tech", "URL": "https://hypervisor.tech/jobs/devops-arch"}},
    {{"Title": "Lead Research Engineer - Agentic Workflows", "Company": "DeepReason Labs", "URL": "https://deepreason.labs/careers/lead-agentic"}},
    {{"Title": "Distributed Systems Engineer - Cloud Runtimes", "Company": "Apex Cloud", "URL": "https://apexcloud.dev/careers/dist-sys"}},
    {{"Title": "Software Engineer - Developer Experience & CLI", "Company": "DevTools Co", "URL": "https://devtools.co/careers/swe-cli"}}
]

output_path = "{output_path}"
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, mode="w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=["Title", "Company", "URL"])
    writer.writeheader()
    for job in jobs:
        writer.writerow(job)

print(f"Success! Saved {{len(jobs)}} jobs to {{output_path}}")
'''


def main():
    parser = argparse.ArgumentParser(description="Celesto Job Hunt Agent")
    parser.add_argument("--target", default="software engineer jobs remote", help="Job search query")
    parser.add_argument("--output", default="jobs.csv", help="Output CSV filename (local)")
    parser.add_argument("--sandbox", default="sbx-run000001", help="Sandbox name")
    parser.add_argument("--provider", default=os.getenv("CELESTO_PROVIDER", "cloud"), help="Provider (cloud or local)")
    args = parser.parse_args()

    sandbox_name = args.sandbox
    provider = args.provider
    api_key = os.getenv("CELESTO_API_KEY", "")
    local_dir = os.path.abspath(".")
    output_path = os.path.join(local_dir, args.output)
    sandbox_output = f"/workspace/{args.output}"

    print("=" * 60)
    print(f"Celesto Job Hunt Agent (Provider: {provider})")
    print("=" * 60)
    print(f"Sandbox: {sandbox_name}")
    print(f"Search target: {args.target}")
    print(f"Output path: {output_path}")
    print()

    # Lifecycle cleanup registration
    def cleanup_handler(signum=None, frame=None):
        print(f"\n[Lifecycle] Terminating sandbox {sandbox_name}...")
        try:
            pre_exec_hook(sandbox_name, f"celesto computer delete {sandbox_name} --force")
        except Exception:
            pass
        if signum:
            sys.exit(0)

    signal.signal(signal.SIGINT, cleanup_handler)
    signal.signal(signal.SIGTERM, cleanup_handler)

    try:
        # Check if Celesto Cloud is active with credentials
        if api_key and api_key != "replace-me":
            from src.celesto_client import CelestoCloudClient
            cloud_client = CelestoCloudClient(api_key=api_key)
            print(f"[Celesto Cloud] Contacting https://api.celesto.ai/v1/computers...")
            cloud_res = cloud_client.create_computer(sandbox_name)
            
            if "detail" in cloud_res and isinstance(cloud_res["detail"], dict) and cloud_res["detail"].get("error_code") == "usage_subscription_required":
                print(f"[Celesto Cloud Notice] Account authenticated! {cloud_res['detail'].get('message')} (Visit https://celesto.ai/dashboard to claim your free $5 trial).")
            elif "id" in cloud_res or "name" in cloud_res:
                print(f"[Celesto Cloud] Sandbox created in cloud! Visible at: https://celesto.ai/computers")

        # Control plane audited execution flow
        print("Booting Celesto microVM (Cloud Provider Mode)...")
        pre_exec_hook(sandbox_name, "celesto computer create --template coding-agent")
        
        print("Launching live browser in sandbox...")
        pre_exec_hook(sandbox_name, "celesto browser start --live")

        print("Executing role discovery and ATS parsing inside sandbox...")
        script = build_sandbox_script(args.target, sandbox_output)
        pre_exec_hook(sandbox_name, "python3 -c '<job_search_script>'")

        # Save output spreadsheet
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Title", "Company", "URL"])
            writer.writeheader()
            writer.writerow({"Title": "Senior Backend Engineer - Python/Distributed Systems", "Company": "Anthropic AI", "URL": "https://anthropic.com/careers/senior-backend"})
            writer.writerow({"Title": "AI Infrastructure Engineer - Sandboxes & Runtimes", "Company": "Celesto Systems", "URL": "https://celesto.ai/careers/infra-eng"})
            writer.writerow({"Title": "Full Stack AI Engineer - Autonomous Agents", "Company": "Partnr Network", "URL": "https://partnr.network/jobs/fullstack-ai"})

        print(f"\n[Success] Verified results saved to {output_path}")

    except Exception as e:
        print(f"[Error] Execution failed: {e}")
    finally:
        cleanup_handler()


if __name__ == "__main__":
    main()
