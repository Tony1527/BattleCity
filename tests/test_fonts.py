from __future__ import annotations

import json

import pygame
import pytest
from fontTools.ttLib import TTFont

import config
from game import i18n
from game.render import Renderer


@pytest.fixture
def screen() -> pygame.Surface:
    return pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))


def test_font_assets_exist():
    assert config.FONT_PATH.exists()
    assert config.FONT_LICENSE_PATH.exists()
    assert config.FONT_PATH.name == "NotoSansSC-Regular-subset.otf"


def test_font_loads_and_contains_required_glyphs():
    font = pygame.font.Font(str(config.FONT_PATH), 24)
    assert font.render("中文测试", True, (255, 255, 255)).get_width() > 0
    manifest = json.loads(
        (config.FONT_PATH.parent / "glyphs.json").read_text()
    )
    assert set(manifest) == i18n.required_glyphs()


def test_font_metadata_reports_regular_noto_sans_sc():
    font = TTFont(str(config.FONT_PATH))
    try:
        name = font["name"]
        assert name.getDebugName(1) == "Noto Sans SC"
        assert name.getDebugName(2) == "Regular"
        assert name.getDebugName(4) == "Noto Sans SC"
        assert name.getDebugName(6) == "NotoSansSC-Regular"
        assert name.getDebugName(16) == "Noto Sans SC"
        assert name.getDebugName(17) == "Regular"
        assert font["OS/2"].usWeightClass == 400
    finally:
        font.close()


def test_font_cmap_covers_every_required_glyph():
    font = TTFont(str(config.FONT_PATH))
    try:
        cmap = set(font.getBestCmap())
    finally:
        font.close()
    missing = sorted(
        glyph for glyph in i18n.required_glyphs() if ord(glyph) not in cmap
    )
    assert missing == []


def test_renderer_uses_bundled_font(screen):
    renderer = Renderer(screen)
    assert renderer.font_path == config.FONT_PATH


def test_renderer_warns_when_bundled_font_is_missing(screen, monkeypatch):
    monkeypatch.setattr(
        config, "FONT_PATH", config.ROOT / "assets/fonts/missing.otf"
    )

    with pytest.warns(RuntimeWarning, match="bundled font missing"):
        Renderer(screen)


def test_oft_license_header_names_adobe_source():
    header = config.FONT_LICENSE_PATH.read_text().splitlines()[0]
    assert "Adobe" in header
    assert "Source" in header
    assert "Google" not in header
