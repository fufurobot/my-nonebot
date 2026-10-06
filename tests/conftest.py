"""Shared pytest fixtures for the chess plugin test-suite.

The plugin modules live under ``src/plugins`` and are loaded by NoneBot at
runtime rather than installed as a package, so the repository root is placed on
``sys.path`` (see ``pythonpath`` in pyproject.toml) and the plugin is imported by
loading ``src/plugins/chess`` as a package.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = REPO_ROOT / "src" / "plugins" / "chess"


def _load_chess_package() -> ModuleType:
    """Import ``src/plugins/chess`` under the name ``chess_plugin``.

    Importing it by directory avoids a name clash with the third-party ``chess``
    library and does not require the plugin to be an installed distribution.

    The package calls ``nonebot.on_command`` at import time, which requires an
    initialized NoneBot instance, so that is set up on first load.
    """
    name = "chess_plugin"
    if name in sys.modules:
        return sys.modules[name]

    import nonebot

    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init(driver="~none", environment="test")

    spec = importlib.util.spec_from_file_location(
        name,
        PLUGIN_DIR / "__init__.py",
        submodule_search_locations=[str(PLUGIN_DIR)],
    )
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load chess plugin from {PLUGIN_DIR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def chess_package() -> ModuleType:
    """The ``src/plugins/chess`` package, loaded once per session."""
    return _load_chess_package()


@pytest.fixture
def game_module(chess_package: ModuleType) -> ModuleType:
    """The ``chess.game`` module holding :class:`ChessGame`."""
    return sys.modules["chess_plugin.game"]


@pytest.fixture
def ChessGame(game_module: ModuleType):
    """The :class:`ChessGame` class."""
    return game_module.ChessGame
