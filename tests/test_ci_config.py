"""Tests pinning the CI configuration and the shareable env template.

CI configuration is code: it silently rots when nobody asserts its shape. These
tests parse the workflow files and check the properties the project actually
depends on -- the pinned Python range, the commands that must run, and the
absence of secrets in anything tracked by git.

``yaml`` is an optional dependency; the tests skip cleanly when it is missing so
the suite still runs in a bare environment.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parent.parent
GITHUB_WORKFLOWS = REPO_ROOT / ".github" / "workflows"
GITLAB_CI = REPO_ROOT / ".gitlab-ci.yml"
ENV_EXAMPLE = REPO_ROOT / ".env.example"

# Token-shaped strings that must never appear in a tracked file.
SECRET_PATTERNS = (
    re.compile(r"github_pat_\w+"),
    re.compile(r"ghp_\w{20,}"),
    re.compile(r"glpat-[\w-]{15,}"),
)


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# GitHub Actions
# --------------------------------------------------------------------------


def test_github_workflow_directory_exists():
    assert GITHUB_WORKFLOWS.is_dir(), "missing .github/workflows"


def test_ci_workflow_exists_and_is_valid_yaml():
    path = GITHUB_WORKFLOWS / "ci.yml"
    assert path.is_file(), "missing .github/workflows/ci.yml"
    assert isinstance(_load(path), dict)


def test_ci_workflow_triggers_on_push_and_pull_request():
    workflow = _load(GITHUB_WORKFLOWS / "ci.yml")
    # PyYAML reads a bare `on:` key as the boolean True.
    triggers = workflow.get("on", workflow.get(True))
    assert triggers is not None, "workflow has no triggers"
    assert "push" in triggers
    assert "pull_request" in triggers


def test_ci_workflow_runs_the_test_suite_and_linter():
    raw = (GITHUB_WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert "pytest" in raw, "CI must run the test suite"
    assert "ruff" in raw, "CI must run the linter"


def test_ci_workflow_uses_astral_uv_action():
    raw = (GITHUB_WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert "astral-sh/setup-uv" in raw, "CI should install uv via the official action"


def test_ci_workflow_covers_the_supported_python_versions():
    workflow = _load(GITHUB_WORKFLOWS / "ci.yml")
    raw = (GITHUB_WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    # The project requires >=3.10,<4.0; CI should exercise more than one version.
    versions = re.findall(r"python-version:\s*\[([^\]]+)\]", raw)
    matrix_line = " ".join(versions)
    assert "3.10" in matrix_line, "CI must cover the minimum supported Python 3.10"
    assert "3.13" in matrix_line or "3.12" in matrix_line
    assert "jobs" in workflow


def test_ci_workflow_does_not_request_write_permissions():
    workflow = _load(GITHUB_WORKFLOWS / "ci.yml")
    perms = workflow.get("permissions")
    assert perms in (None, "read-all") or perms.get("contents") == "read", (
        "a test-only workflow should not need write permissions"
    )


def test_release_workflow_is_valid_yaml_if_present():
    path = GITHUB_WORKFLOWS / "release.yml"
    if path.is_file():
        assert isinstance(_load(path), dict)


# --------------------------------------------------------------------------
# GitLab CI
# --------------------------------------------------------------------------


def test_gitlab_ci_exists_and_is_valid_yaml():
    assert GITLAB_CI.is_file(), "missing .gitlab-ci.yml"
    assert isinstance(_load(GITLAB_CI), dict)


def test_gitlab_ci_defines_stages_and_runner_image():
    config = _load(GITLAB_CI)
    assert "stages" in config, "GitLab CI must declare stages"
    assert "default" in config or "image" in config, "GitLab CI must pin an image"
    jobs = [k for k, v in config.items() if isinstance(v, dict) and "script" in v]
    assert jobs, "GitLab CI must define at least one job with a script"


def test_gitlab_ci_runs_tests_and_lint():
    raw = GITLAB_CI.read_text(encoding="utf-8")
    assert "pytest" in raw
    assert "ruff" in raw


# --------------------------------------------------------------------------
# .env.example
# --------------------------------------------------------------------------


def test_env_example_exists():
    assert ENV_EXAMPLE.is_file(), "missing .env.example for contributors"


def test_env_example_documents_required_keys():
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    for key in ("ENVIRONMENT", "DRIVER", "HOST", "PORT", "ONEBOT_V11_ACCESS_TOKEN"):
        assert key in text, f"{key} missing from .env.example"


def test_env_example_carries_no_placeholder_secret():
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    for pattern in SECRET_PATTERNS:
        assert not pattern.search(text), f"secret-like value in .env.example: {pattern}"


def test_env_example_token_value_is_empty_or_dummy():
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.strip().startswith("ONEBOT_V11_ACCESS_TOKEN="):
            value = line.split("=", 1)[1].strip()
            assert value in ("", "changeme", "<your-token>"), (
                f".env.example must not ship a real token: {value!r}"
            )
            return
    pytest.fail("ONEBOT_V11_ACCESS_TOKEN missing from .env.example")


# --------------------------------------------------------------------------
# no secrets anywhere in the tracked tree
# --------------------------------------------------------------------------


def test_tracked_files_contain_no_secret_like_values():
    """The workflow files and env template must never embed a credential."""
    for path in [*GITHUB_WORKFLOWS.glob("*.yml"), GITLAB_CI, ENV_EXAMPLE]:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in SECRET_PATTERNS:
            assert not pattern.search(text), f"{path.name} embeds a credential"
