from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


def read_env_value(env_path: Path, key: str) -> Optional[str]:
    if not env_path.exists():
        return None
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            if not raw or raw.strip().startswith("#"):
                continue
            if raw.startswith(f"{key}="):
                return raw.split("=", 1)[1].strip()
    except Exception:
        return None
    return None


def stop_process_on_port_windows(port: int) -> None:
    """Stop any process bound to the given TCP local port (Windows/PowerShell)."""
    ps_cmd = (
        f"$p=(Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue)"
        f"|Select-Object -ExpandProperty OwningProcess -Unique;"
        f" if ($p) {{ Stop-Process -Id $p -Force -ErrorAction SilentlyContinue;"  # noqa: E501
        f" Write-Output \"Stopped PID $p on port {port}\" }}"
        f" else {{ Write-Output \"No process on port {port}\" }}"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except FileNotFoundError:
        # PowerShell not found; ignore gracefully
        pass


def start_relay(env_path: Path, host: str = "127.0.0.1", port: int = 8787) -> subprocess.Popen:
    push_token = read_env_value(env_path, "PUSH_TOKEN") or "CHANGE_ME_PUSH_TOKEN"
    allow_clients = read_env_value(env_path, "ALLOW_CLIENTS") or "minato-pc-01"

    child_env = os.environ.copy()
    child_env["PUSH_TOKEN"] = push_token
    child_env["ALLOW_CLIENTS"] = allow_clients

    stop_process_on_port_windows(port)
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "relay_server:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    return subprocess.Popen(cmd, env=child_env)


def start_listener(env_path: Path, http_host: str = "127.0.0.1", http_port: int = 8789,
                   relay_host: str = "127.0.0.1", relay_port: int = 8787,
                   client_id: str = "minato-pc-01") -> subprocess.Popen:
    push_token = read_env_value(env_path, "PUSH_TOKEN") or "CHANGE_ME_PUSH_TOKEN"

    child_env = os.environ.copy()
    child_env["UCAR_WSS"] = f"ws://{relay_host}:{relay_port}/alerts"
    child_env["PUSH_TOKEN"] = push_token
    child_env["UCAR_PUSH_TOKEN"] = push_token
    child_env["UCAR_CLIENT_ID"] = client_id
    child_env["CLIENT_ID"] = client_id
    child_env["UCAR_HTTP_HOST"] = http_host
    child_env["UCAR_HTTP_PORT"] = str(http_port)

    stop_process_on_port_windows(http_port)
    cmd = [sys.executable, "ucar_rt_listener.py"]
    return subprocess.Popen(cmd, env=child_env)


def wait_health(url: str, timeout_sec: float = 5.0) -> bool:
    try:
        import httpx  # type: ignore

        with httpx.Client(timeout=timeout_sec) as client:
            r = client.get(url)
            return r.status_code == 200
    except Exception:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Start/Restart UCAR relay and listener.")
    parser.add_argument("--relay", action="store_true", help="Restart relay (8787)")
    parser.add_argument("--listener", action="store_true", help="Restart listener (8789)")
    parser.add_argument("--client-id", default="minato-pc-01")
    args = parser.parse_args()

    if not args.relay and not args.listener:
        # Default: both
        args.relay = True
        args.listener = True

    project_root = Path(__file__).resolve().parent
    env_path = project_root / ".env"

    relay_proc = None
    listener_proc = None

    if args.relay:
        relay_proc = start_relay(env_path)
        # small grace period
        time.sleep(1.0)
        ok = wait_health("http://127.0.0.1:8787/health", timeout_sec=3.0)
        print(f"Relay health: {'OK' if ok else 'NG'}")

    if args.listener:
        listener_proc = start_listener(env_path, client_id=args.client_id)
        print("Listener started.")

    # Print PIDs so user can manage processes
    if relay_proc:
        print(f"Relay PID: {relay_proc.pid}")
    if listener_proc:
        print(f"Listener PID: {listener_proc.pid}")


if __name__ == "__main__":
    main()


