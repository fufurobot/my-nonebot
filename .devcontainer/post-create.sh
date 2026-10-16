#!/usr/bin/env bash
#
# Codespaces bootstrap for dsh-bot.
#
# The container is a plain Ubuntu base, so nothing may be assumed about which
# language runtimes are preinstalled -- and the base image's Python is not
# necessarily a version this project supports (it requires 3.10-3.13). Every
# tool is therefore installed through its official installer, and the Python
# interpreter is left to `uv`, which downloads a matching one on demand.
#
# This script must be idempotent: Codespaces runs it again after a rebuild.
set -euo pipefail

echo "==> Installing uv (official installer)"
if ! command -v uv >/dev/null 2>&1; then
  # The installer and uv both live in $HOME, which is writable in Codespaces.
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

# Shells opened later in the Codespace need uv on PATH too. `uv`'s installer
# writes to the profile, but a non-login shell (which is what the terminal
# starts) may not read it, so this is belt and braces.
if ! grep -q 'HOME/.local/bin' "$HOME/.bashrc" 2>/dev/null; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >>"$HOME/.bashrc"
fi

echo "==> uv $(uv --version)"
echo "==> Syncing project dependencies"
# A committed uv.lock would make this reproducible; the project gitignores it,
# so this resolves fresh and pins a supported interpreter.
uv sync --all-groups

echo "==> Installing a supported Python for the project"
# `uv python install` uses the project's requires-python (>=3.10,<4.0).
uv python install 3.13

echo "==> Verifying the toolchain"
uv run python --version
uv run pytest tests -q

echo "==> Preparing the local environment file"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "    created .env from .env.example (fill in your own ONEBOT_V11_ACCESS_TOKEN)"
fi

cat <<'DONE'

Codespace ready.

Next steps:
  1. Set ONEBOT_V11_ACCESS_TOKEN in .env to match your QQ client.
  2. Put any GitHub tooling token in .env.tooling, never in .env -- the bot logs
     its whole config at LOG_LEVEL=DEBUG.
  3. Run the bot with: uv run nb run
DONE
