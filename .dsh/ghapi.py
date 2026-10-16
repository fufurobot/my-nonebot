#!/usr/bin/env python3
"""Reusable GitHub REST client for the agent (Linux-safe).

The repo's original ``.dsh/gh.py`` shells out to an MSYS2 ``curl`` because
Python's TLS stack was broken on the Windows host. On Linux ``urllib`` works
fine, and the DSH sandbox blocks ``curl`` outright, so this module talks to the
API directly over ``urllib``.

The token is read from (in order) ``$GITHUB_TOKEN``, the ``GITHUB_TOKEN=`` line
of ``.env.tooling``, then ``.env`` -- the first two are gitignored and are NOT
loaded by the bot, so NoneBot's ``LOG_LEVEL=DEBUG`` config dump can never print
them.

Usage:
    python .dsh/ghapi.py GET /repos/owner/repo
    python .dsh/ghapi.py POST /repos/owner/repo/issues '{"title": "..."}'
    python .dsh/ghapi.py GET /repos/owner/repo --jq .full_name
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"
REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILES = (REPO_ROOT / ".env.tooling", REPO_ROOT / ".env")
USER_AGENT = "dsh-bot-agent"


def token() -> str:
    """Return the GitHub token, or raise if none is configured."""
    env_token = os.environ.get("GITHUB_TOKEN")
    if env_token:
        return env_token.strip()
    for path in ENV_FILES:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("GITHUB_TOKEN="):
                value = line.split("=", 1)[1].strip()
                if value:
                    return value
    msg = "no GITHUB_TOKEN in the environment, .env.tooling or .env"
    raise RuntimeError(msg)


def request(
    method: str,
    path: str,
    payload: object | None = None,
    *,
    token_value: str | None = None,
    api: str = API,
) -> tuple[int, object]:
    """Perform one API call and return ``(status, decoded_body)``.

    ``path`` may be a path such as ``/repos/o/r`` or a full URL, which is what
    the ``Link`` header pagination needs.
    """
    url = path if path.startswith("http") else f"{api}{path}"
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    auth = token_value if token_value is not None else token()
    if auth:
        headers["Authorization"] = f"Bearer {auth}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:  # noqa: PERF203 - single call site
        raw = exc.read().decode("utf-8", "replace")
        try:
            body: object = json.loads(raw)
        except ValueError:
            body = raw
        return exc.code, body


def main(argv: list[str]) -> int:
    if len(argv) < 3:  # noqa: PLR2004 - argv shape, not a magic constant
        print(__doc__)
        return 2
    method, path = argv[1].upper(), argv[2]
    payload = json.loads(argv[3]) if len(argv) > 3 and argv[3] != "-" else None
    status, body = request(method, path, payload)
    print(json.dumps(body, ensure_ascii=False, indent=2))
    return 0 if status < 400 else 1  # noqa: PLR2004 - HTTP status boundary


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
