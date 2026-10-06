#!/usr/bin/env python3
"""Tiny GitHub REST helper used by the agent while implementing CI.

Python's own TLS stack is unusable in this environment (schannel/urllib both
fail), but the MSYS2 `curl` binary works. So this helper shells out to curl and
only uses Python for argument handling and JSON pretty-printing.

Reads the token from the GITHUB_TOKEN environment variable, falling back to the
GITHUB_TOKEN= line of the repo-root .env file (which is gitignored).

Usage:
    python .dsh/gh.py GET  /repos/owner/repo
    python .dsh/gh.py POST /repos/owner/repo/issues  '{"title": "..."}'
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

API = "https://api.github.com"
CURL_CANDIDATES = (
    r"C:\Users\fufu\Downloads\msys64\clang64\bin\curl.exe",
    r"C:\Users\fufu\Downloads\msys64\usr\bin\curl.exe",
    "curl",
)


def token() -> str:
    env = os.environ.get("GITHUB_TOKEN")
    if env:
        return env.strip()
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GITHUB_TOKEN="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("no GITHUB_TOKEN in environment or .env")


def curl_binary() -> str:
    for cand in CURL_CANDIDATES:
        if cand == "curl" or Path(cand).is_file():
            return cand
    raise SystemExit("no curl binary found")


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    method, path = argv[1].upper(), argv[2]
    body: str | None = None
    body_file: Path | None = None
    if len(argv) > 3 and argv[3]:
        # A leading '@' means "read the payload from this file". Handing curl the
        # file directly (--data-binary @file) avoids re-encoding a long body on
        # the Windows command line, which corrupts non-ASCII JSON.
        if argv[3].startswith("@"):
            body_file = Path(argv[3][1:]).resolve()
            if not body_file.is_file():
                raise SystemExit(f"payload file not found: {body_file}")
        else:
            body = argv[3]
    url = path if path.startswith("http") else API + path

    cmd = [
        curl_binary(),
        "-sS",
        "-m",
        "60",
        "-X",
        method,
        "-H",
        f"Authorization: Bearer {token()}",
        "-H",
        "Accept: application/vnd.github+json",
        "-H",
        "X-GitHub-Api-Version: 2022-11-28",
        "-H",
        "User-Agent: dsh-agent",
        "-w",
        "\n%{http_code}",
    ]
    if body_file is not None:
        cmd += [
            "-H",
            "Content-Type: application/json; charset=utf-8",
            "--data-binary",
            f"@{body_file}",
        ]
    elif body is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", body]
    cmd.append(url)

    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        return proc.returncode

    payload, _, code = proc.stdout.rpartition("\n")
    status = int(code.strip() or 0)
    print(payload)
    print(status, file=sys.stderr)

    try:
        data = json.loads(payload) if payload.strip() else None
    except json.JSONDecodeError:
        return 0 if status < 400 else 1

    if isinstance(data, list) and data and isinstance(data[0], dict):
        keys = ("number", "full_name", "name", "state", "status", "conclusion", "title")
        for item in data:
            print(
                "  " + " | ".join(f"{k}={item[k]}" for k in keys if k in item),
                file=sys.stderr,
            )
    elif isinstance(data, dict):
        for k in (
            "number",
            "full_name",
            "state",
            "status",
            "conclusion",
            "title",
            "html_url",
            "total_count",
            "message",
        ):
            if k in data:
                print(f"  {k}={data[k]}", file=sys.stderr)
    return 0 if status < 400 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
