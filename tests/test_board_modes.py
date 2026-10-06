"""Tests for per-group board template selection.

The chat command ``chess mode`` reads and writes a per-group preference, so the
selection logic is worth pinning independently of the chat handler.
"""

from __future__ import annotations

import chess
import pytest


@pytest.fixture
def plugin(chess_package):
    return chess_package


def test_default_mode_is_compact_for_a_fresh_group(plugin):
    plugin.board_modes.clear()
    assert plugin._mode_for(424242) == "compact"


def test_mode_selection_is_per_group(plugin):
    plugin.board_modes.clear()
    plugin.board_modes[1] = "normal"
    assert plugin._mode_for(1) == "normal"
    assert plugin._mode_for(2) == "compact", "another group keeps the default"


def test_mode_for_falls_back_when_selection_is_stale(plugin):
    """A stored mode that no longer has a template must not crash rendering."""
    plugin.board_modes[7] = "some-removed-mode"
    assert plugin._mode_for(7) == plugin.board_templates.DEFAULT_MODE


def test_help_text_advertises_the_mode_command(plugin):
    assert "chess mode" in plugin.HELP_TEXT


def test_help_text_lists_every_available_template(plugin):
    for mode in plugin.board_templates.AVAILABLE_MODES:
        assert mode in plugin.HELP_TEXT, f"{mode} not advertised in help"


def test_available_modes_include_compact_and_normal(plugin):
    assert set(plugin.board_templates.AVAILABLE_MODES) == {"compact", "normal"}


def test_every_advertised_mode_renders(plugin):
    for mode in plugin.board_templates.AVAILABLE_MODES:
        text = plugin.board_templates.render(chess.Board(), mode)
        assert text.strip(), f"{mode} produced empty output"


def test_compact_mode_is_default_in_templates_module(plugin):
    assert plugin.board_templates.DEFAULT_MODE == "compact"


def test_demo_render_for_each_mode_is_within_the_compact_limit(plugin):
    for mode in plugin.board_templates.AVAILABLE_MODES:
        text = plugin.board_templates.render(chess.Board(), mode)
        if mode != "compact":
            continue
        for line in text.splitlines():
            assert len(line) <= 13, f"compact demo line too wide: {line!r}"


def test_render_accepts_none_as_default(plugin):
    default = plugin.board_templates.render(chess.Board(), None)
    explicit = plugin.board_templates.render(chess.Board(), "compact")
    assert default == explicit


def test_modes_helper_matches_available(plugin):
    assert (
        tuple(plugin.board_templates.modes()) == plugin.board_templates.AVAILABLE_MODES
    )


def test_plugin_module_exposes_board_modes_registry(plugin):
    assert isinstance(plugin.board_modes, dict)
