#!/usr/bin/env python3
"""GitHub OAuth device-flow login.

Device flow exists so a tool can obtain a user access token without a browser
redirect and without the user pasting a PAT. The user opens a verification URL,
types a short code, and the tool polls until GitHub hands back a token.

Usage:
    python .dsh/device_login.py start     # print the code and the URL to visit
    python .dsh/device_login.py poll      # poll until the token arrives
    python .dsh/device_login.py login     # start then poll

Credentials come from the environment or the gitignored `.env.tooling`:

    GITHUB_OAUTH_CLIENT_ID
    GITHUB_OAUTH_CLIENT_SECRET   (optional for public clients)

The client secret is never printed by this script, and the resulting token is
written only to `.env.tooling`, never to stdout or a tracked file.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from gh import curl_binary  # reuse the curl discovery that already works here

DEVICE_CODE_URL = "https://github.com/login/device/code"
TOKEN_URL = "https://github.com/login/oauth/access_token"
VERIFY_URL = "https://github.com/login/device"

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLING_ENV = REPO_ROOT / ".env.tooling"
STATE_FILE = Path(__file__).resolve().parent / ".device_state.json"

#: Scopes requested for the token. `repo` is needed to open issues and pull
#: requests on a private repository; narrow this if you only need public access.
DEFAULT_SCOPES = "repo read:user"


def read_env(name: str) -> str | None:
    """Read ``name`` from the environment, then from `.env.tooling`."""
    value = os.environ.get(name)
    if value:
        return value.strip()
    if TOOLING_ENV.is_file():
        for line in TOOLING_ENV.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith(f"{name}="):
                found = line.split("=", 1)[1].strip()
                if found:
                    return found
    return None


def _post(url: str, data: dict[str, str]) -> dict[str, Any]:
    cmd = [
        curl_binary(),
        "-sS",
        "-m",
        "60",
        "-X",
        "POST",
        "-H",
        "Accept: application/json",
        "-H",
        "User-Agent: dsh-agent",
    ]
    for key, value in data.items():
        cmd += ["-d", f"{key}={value}"]
    cmd.append(url)
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise SystemExit(f"request failed: {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise SystemExit(f"unexpected non-JSON response from {url}") from None


def start() -> dict[str, Any]:
    """Request a device code and persist it for the polling step."""
    client_id = read_env("GITHUB_OAUTH_CLIENT_ID")
    if not client_id:
        raise SystemExit("GITHUB_OAUTH_CLIENT_ID is not set (see .env.tooling)")

    payload = _post(DEVICE_CODE_URL, {"client_id": client_id, "scope": DEFAULT_SCOPES})
    if "device_code" not in payload:
        raise SystemExit(f"GitHub refused the device-code request: {payload}")

    STATE_FILE.write_text(json.dumps(payload), encoding="utf-8")
    STATE_FILE.chmod(0o600)

    print("Visit this URL in a browser:", file=sys.stderr)
    print(f"  {payload.get('verification_uri', VERIFY_URL)}", file=sys.stderr)
    print("and enter this code:", file=sys.stderr)
    print(f"  {payload['user_code']}", file=sys.stderr)
    print(
        f"\nThe code expires in {payload.get('expires_in', 900) // 60} minutes.",
        file=sys.stderr,
    )
    return payload


def poll() -> str | None:
    """Poll until GitHub issues a token, or the code expires."""
    client_id = read_env("GITHUB_OAUTH_CLIENT_ID")
    if not client_id:
        raise SystemExit("GITHUB_OAUTH_CLIENT_ID is not set (see .env.tooling)")
    if not STATE_FILE.is_file():
        raise SystemExit("no pending device code; run 'start' first")

    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    device_code = state["device_code"]
    interval = int(state.get("interval", 5))
    deadline = time.time() + int(state.get("expires_in", 900))

    body = {"client_id": client_id, "device_code": device_code}
    # The secret is only sent when present; public clients omit it entirely.
    secret = read_env("GITHUB_OAUTH_CLIENT_SECRET")
    if secret:
        body["client_secret"] = secret

    while time.time() < deadline:
        payload = _post(TOKEN_URL, {**body, "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
        error = payload.get("error")

        if payload.get("access_token"):
            STATE_FILE.unlink(missing_ok=True)
            return payload["access_token"]
        if error == "authorization_pending":
            time.sleep(interval)
            continue
        if error == "slow_down":
            interval += 5
            time.sleep(interval)
            continue
        if error in ("expired_token", "access_denied"):
            STATE_FILE.unlink(missing_ok=True)
            raise SystemExit(f"login failed: {error}")
        raise SystemExit(f"unexpected response: {payload}")

    raise SystemExit("device code expired before authorization completed")


def store_token(token: str) -> None:
    """Write the token into `.env.tooling`, replacing any existing value."""
    lines: list[str] = []
    replaced = False
    if TOOLING_ENV.is_file():
        for line in TOOLING_ENV.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GITHUB_TOKEN="):
                lines.append(f"GITHUB_TOKEN={token}")
                replaced = True
            else:
                lines.append(line)
    if not replaced:
        lines.append(f"GITHUB_TOKEN={token}")
    TOOLING_ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    action = argv[1] if len(argv) > 1 else "login"

    if action == "start":
        start()
        return 0

    if action == "poll":
        token = poll()
        if token:
            print("authorized; token obtained", file=sys.stderr)
        return 0

    if action == "login":
        start()
        print("\nWaiting for authorization...", file=sys.stderr)
        token = poll()
        if token:
            store_token(token)
            print("token stored in .env.tooling", file=sys.stderr)
        return 0

    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main(sys.argv))
