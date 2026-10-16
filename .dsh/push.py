#!/usr/bin/env python3
"""Push to the GitHub remote over HTTPS using the token.

The repository's ``origin`` is an SSH URL, which this sandbox cannot use (there
is no ``ssh.exe`` and no agent). Rather than rewrite ``origin`` -- which would
leave a credential-bearing URL in ``.git/config`` -- this script feeds the token
to ``git`` through a one-shot ``GIT_ASKPASS`` helper, so the credential never
appears on a command line, in the process table, in ``.git/config`` or in this
script's output.

Usage:
    python .dsh/push.py <branch> [--set-upstream]
    python .dsh/push.py main
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HTTPS_REMOTE = "https://github.com/fufurobot/my-nonebot.git"


def token() -> str:
    """Read the token from the environment or the gitignored tooling env file."""
    env_token = os.environ.get("GITHUB_TOKEN")
    if env_token:
        return env_token.strip()
    for path in (REPO_ROOT / ".env.tooling", REPO_ROOT / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("GITHUB_TOKEN="):
                value = line.split("=", 1)[1].strip()
                if value:
                    return value
    msg = "no GITHUB_TOKEN in the environment, .env.tooling or .env"
    raise RuntimeError(msg)


def main(argv: list[str]) -> int:
    if len(argv) < 2:  # noqa: PLR2004 - argv shape
        print(__doc__)
        return 2
    branch = argv[1]
    set_upstream = "--set-upstream" in argv

    # The askpass helper prints the password git asks for. It is written to a
    # private temp file and deleted immediately after the push.
    with tempfile.TemporaryDirectory() as tmp:
        helper = Path(tmp) / "askpass.sh"
        # `%s` is git's prompt; we always answer with the token.
        helper.write_text(
            "#!/bin/sh\n"
            f"cat {Path(tmp) / 'token'}\n",
            encoding="utf-8",
        )
        (Path(tmp) / "token").write_text(token(), encoding="utf-8")
        helper.chmod(0o700)
        (Path(tmp) / "token").chmod(0o600)

        env = {
            **os.environ,
            "GIT_ASKPASS": str(helper),
            "GIT_TERMINAL_PROMPT": "0",
        }
        cmd = ["git", "push", HTTPS_REMOTE, f"refs/heads/{branch}:refs/heads/{branch}"]
        if set_upstream:
            cmd.insert(2, "--set-upstream")
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell
            cmd, cwd=REPO_ROOT, env=env, check=False
        )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
