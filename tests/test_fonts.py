from __future__ import annotations

import json

import pygame
import pytest

import config
from game import i18n
from game.render import Renderer


@pytest.fixture
def screen() -> pygame.Surface:
    return pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))


def test_font_assets_exist():
    assert config.FONT_PATH.exists()
    assert config.FONT_LICENSE_PATH.exists()


def test_font_loads_and_contains_required_glyphs():
    font = pygame.font.Font(str(config.FONT_PATH), 24)
    assert font.render("中文测试", True, (255, 255, 255)).get_width() > 0
    manifest = json.loads(
        (config.FONT_PATH.parent / "glyphs.json").read_text()
    )
    assert set(manifest) == i18n.required_glyphs()


def test_renderer_uses_bundled_font(screen):
    renderer = Renderer(screen)
    assert renderer.font_path == config.FONT_PATH
