"""
scripts/start_servers.py
========================
Unified Production Server Launcher for Nassau Candy Logistics Analytics Platform.

Spawns and orchestrates both services concurrently:
  - Port 8501: Logistics Analytics & BI Platform (dashboard/app.py)
  - Port 8600: Developer IAM & Control Portal (developer_portal/dev_app.py)

Usage:
  python scripts/start_servers.py
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BANNER = r"""
================================================================================
    _   _____   __________  ___   __  __   _________    _   ______  __  __
   / | / /   | / ___/ ___//   | / / / /  / ____/   |  / | / / __ \/ / / /
  /  |/ / /| | \__ \\__ \/ /| |/ / / /  / /   / /| | /  |/ / / / / /_/ / 
 / /|  / ___ |___/ /__/ / ___ / /_/ /  / /___/ ___ |/ /|  / /_/ / __  /  
/_/ |_/_/  |_/____/____/_/  |_\____/   \____/_/  |_/_/ |_/_____/_/ /_/   
              ENTERPRISE LOGISTICS INTELLIGENCE & IAM PORTAL
================================================================================
"""

SERVICES = [
    {
        "name": "Logistics Analytics Platform",
        "port": 8501,
        "entry": "dashboard/app.py",
        "url": "http://localhost:8501",
        "desc": "Executive BI, Route Intelligence, Delay ML, Financials & Operations",
    },
    {
        "name": "Developer IAM & Control Portal",
        "port": 8600,
        "entry": "developer_portal/dev_app.py",
        "url": "http://localhost:8600",
        "desc": "Cryptographic Key IAM, Workstations, Registration IDs, DB Engine",
    },
]


def launch_services():
    print(BANNER)
    print(f"Working Directory: {ROOT}")
    print(f"Python Runtime:    {sys.executable}")
    print("-" * 80)

    processes = []

    try:
        for svc in SERVICES:
            cmd = [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(ROOT / svc["entry"]),
                "--server.port",
                str(svc["port"]),
                "--server.headless",
                "true",
                "--browser.gatherUsageStats",
                "false",
            ]
            print(f"[+] Starting {svc['name']} on {svc['url']} ...")
            proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                env=os.environ.copy(),
            )
            processes.append((svc, proc))

        print("\n" + "=" * 80)
        print("🚀 ALL SERVICES SUCCESSFULLY STARTED")
        print("=" * 80)
        for svc, _ in processes:
            print(f"  • {svc['name']:<32} -> {svc['url']}")
            print(f"    Purpose: {svc['desc']}\n")

        print("Press Ctrl+C to terminate all services gracefully.\n")

        while True:
            time.sleep(1)
            for svc, proc in processes:
                poll = proc.poll()
                if poll is not None:
                    print(f"\n[!] Service {svc['name']} terminated unexpectedly (exit code {poll}). Shutting down...")
                    return

    except KeyboardInterrupt:
        print("\n\n[~] Received shutdown signal (Ctrl+C). Terminating all services...")
    finally:
        for svc, proc in processes:
            if proc.poll() is None:
                print(f"[-] Terminating {svc['name']} (PID {proc.pid})...")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        print("[✓] All services stopped cleanly.")


if __name__ == "__main__":
    launch_services()
