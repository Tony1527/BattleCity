from __future__ import annotations

import pygame
import pytest

import config
from game import i18n, upgrades
from game.audio import Audio
from game.render import Renderer
from game.states import Game


@pytest.fixture
def screen() -> pygame.Surface:
    return pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))


def key_event(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key)


def test_language_key_sets_match():
    assert set(i18n.TEXTS["zh"]) == set(i18n.TEXTS["en"])


def test_every_upgrade_has_both_translations():
    for upgrade in upgrades.UPGRADE_POOL:
        assert upgrade.name_key in i18n.TEXTS["zh"]
        assert upgrade.name_key in i18n.TEXTS["en"]
        assert upgrade.desc_key in i18n.TEXTS["zh"]
        assert upgrade.desc_key in i18n.TEXTS["en"]


def test_tr_formats_and_falls_back():
    assert i18n.tr("zh", "hud.hp", current=2, maximum=3)
    assert i18n.tr("xx", "hud.hp", current=2, maximum=3)


def test_renderer_switches_language_without_error(screen):
    renderer = Renderer(screen)
    renderer.set_language("en")
    renderer.draw_title(0.0, "normal")
    renderer.set_language("zh")
    renderer.draw_title(0.0, "hell")


def test_all_keys_and_glyphs_cover_language_data():
    assert i18n.all_keys() == set(i18n.TEXTS["zh"])
    glyphs = i18n.required_glyphs()
    assert set("abcdefghijklmnopqrstuvwxyz") <= glyphs
    assert set("0123456789") <= glyphs
    assert set("{}<>/-+.%") <= glyphs
    for text in i18n.TEXTS["zh"].values():
        assert set(text) <= glyphs


def test_language_toggle_updates_game_and_renderer(screen):
    game = Game(screen, seed=5, audio=Audio(enabled=False))
    assert game.language == "zh"
    assert game.renderer.language == "zh"

    game.handle_event(key_event(pygame.K_l))

    assert game.language == "en"
    assert game.renderer.language == "en"
    assert game.difficulty == "normal"

    game.handle_event(key_event(config.CONFIRM_KEY))
    game.handle_event(key_event(pygame.K_l))
    assert game.language == "zh"
    assert game.renderer.language == "zh"

    game.handle_event(key_event(config.CONFIRM_KEY))
    game.handle_event(key_event(config.PAUSE_KEY))
    game.handle_event(key_event(pygame.K_l))
    assert game.language == "en"
    assert game.renderer.language == "en"
