"""Tests for the GitHub Pages site builder.

The site is generated from ``README.md`` at deploy time, so a broken renderer
would publish a broken page without failing anything. These tests run the
builder against the real README and assert the properties a visitor depends on:
tables and code blocks survive, no Markdown syntax leaks through, and the
board glyphs -- which are the whole point of the plugin -- are not mangled.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILDER = REPO_ROOT / ".github" / "scripts" / "build_site.py"
README = REPO_ROOT / "README.md"


@pytest.fixture(scope="module")
def site_builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_site", BUILDER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_site"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rendered(site_builder: ModuleType) -> str:
    return site_builder.to_html(README.read_text(encoding="utf-8"))


def test_builder_exists():
    assert BUILDER.is_file(), "missing the Pages site builder"


def test_pages_workflow_exists_and_uses_the_official_actions():
    workflow = (REPO_ROOT / ".github" / "workflows" / "pages.yml").read_text(
        encoding="utf-8"
    )
    for action in (
        "actions/configure-pages",
        "actions/deploy-pages",
        "upload-pages-artifact",
    ):
        assert action in workflow, f"pages.yml must use {action}"


def test_pages_workflow_declares_the_required_permissions():
    workflow = (REPO_ROOT / ".github" / "workflows" / "pages.yml").read_text(
        encoding="utf-8"
    )
    # Pages deployment needs exactly these; without them the deploy step 403s.
    assert "pages: write" in workflow
    assert "id-token: write" in workflow


def test_renders_headings(rendered: str):
    assert "<h1>dsh-bot</h1>" in rendered
    assert "<h2>" in rendered


def test_renders_tables(rendered: str):
    """The command reference is a table; losing it loses the documentation."""
    assert "<table>" in rendered
    assert "<th>" in rendered
    assert "chess ai" in rendered


def test_renders_fenced_code_blocks(rendered: str):
    assert "<pre><code" in rendered
    assert "</code></pre>" in rendered


def test_escapes_html_inside_code_but_keeps_it_literal(rendered: str):
    """Code blocks must not be interpreted as markup."""
    assert "<script>" not in rendered


def test_leaves_no_markdown_syntax_behind(rendered: str):
    assert not any(line.startswith("#") for line in rendered.splitlines()), (
        "a heading leaked through unrendered"
    )
    assert "](" not in rendered, "an unrendered Markdown link leaked through"


def test_preserves_the_compact_board_characters(rendered: str):
    """The fullwidth glyphs are the reason the compact format exists."""
    assert "♜" in rendered, "chess glyphs were lost"
    assert "ａ" in rendered, "fullwidth file letters were lost"
    assert "\u3000" in rendered, "the ideographic space was lost"


def test_main_writes_the_site(site_builder: ModuleType, tmp_path, monkeypatch):
    monkeypatch.setattr(site_builder, "OUT_DIR", tmp_path / "site")
    assert site_builder.main() == 0
    index = tmp_path / "site" / "index.html"
    assert index.is_file()
    assert "dsh-bot" in index.read_text(encoding="utf-8")


def test_builder_uses_only_the_standard_library(site_builder: ModuleType):
    """CI must not need PyPI to publish the docs."""
    source = BUILDER.read_text(encoding="utf-8")
    for third_party in ("import markdown", "from markdown"):
        assert third_party not in source, "the builder must stay dependency-free"
