from __future__ import annotations

import pygame
import pytest

import config
from game.audio import Audio
from game.states import Game
from game.world import World


def key_event(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key)


@pytest.fixture
def screen() -> pygame.Surface:
    return pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))


@pytest.fixture
def game(screen: pygame.Surface) -> Game:
    return Game(screen, seed=7, audio=Audio(enabled=False))


def start_playing(game: Game) -> None:
    game.handle_event(key_event(config.CONFIRM_KEY))
    assert game.state == "controls"
    game.handle_event(key_event(config.CONFIRM_KEY))
    assert game.state == "playing"


def test_game_starts_on_title(screen):
    game = Game(screen, seed=3, audio=Audio(enabled=False))

    assert game.state == "title"
    assert game.running is True
    assert game.renderer is not None
    assert game.world is not None


def test_enter_on_title_opens_controls(game):
    game.handle_event(key_event(config.CONFIRM_KEY))

    assert game.state == "controls"


def test_enter_on_controls_starts_level_zero(game):
    start_playing(game)

    assert game.level_index == 0
    assert game.world.level_index == 0
    assert game.world.status == "playing"


def test_escape_pauses_and_freezes_simulation(game):
    start_playing(game)
    game.update(0.05)
    elapsed = game.world.elapsed
    assert elapsed > 0.0

    game.handle_event(key_event(config.PAUSE_KEY))
    assert game.state == "paused"

    game.update(1.0)
    assert game.world.elapsed == pytest.approx(elapsed)

    game.handle_event(key_event(config.PAUSE_KEY))
    assert game.state == "playing"

    game.update(0.05)
    assert game.world.elapsed > elapsed


def test_level_clear_offers_upgrades_to_both_players(game):
    start_playing(game)
    game.world.status = "cleared"

    game.update(1 / 60)

    assert game.state == "upgrade"
    assert game.chooser == 0
    assert len(game.offers[0]) == 3
    assert len(game.offers[1]) == 3
    assert all(offer.id for offer in game.offers[0])


def test_players_choose_upgrades_in_order_then_next_level(game):
    start_playing(game)
    game.world.status = "cleared"
    game.update(1 / 60)
    first_offers = list(game.offers[0])
    second_offers = list(game.offers[1])

    game.handle_event(key_event(config.CHOICE_KEYS[0]))

    assert game.state == "upgrade"
    assert game.chooser == 1
    assert game.world.upgrade_levels[0][first_offers[0].id] == 1
    assert game.world.upgrade_levels[1] == {}

    game.handle_event(key_event(config.CHOICE_KEYS[0]))

    assert game.state == "playing"
    assert game.level_index == 1
    assert game.world.level_index == 1
    assert game.world.upgrade_levels[0][first_offers[0].id] == 1
    assert game.world.upgrade_levels[1][second_offers[0].id] == 1


def test_eliminated_player_is_skipped_for_upgrades(game):
    start_playing(game)
    game.world.players[0].eliminated = True
    game.world.players[0].alive = False
    game.world.status = "cleared"

    game.update(1 / 60)

    assert game.state == "upgrade"
    assert game.chooser == 1
    assert game.offers[0] == []
    assert len(game.offers[1]) == 3

    chosen = game.offers[1][0]
    game.handle_event(key_event(config.CHOICE_KEYS[0]))

    assert game.state == "playing"
    assert game.level_index == 1
    assert game.world.upgrade_levels[0] == {}
    assert game.world.upgrade_levels[1][chosen.id] == 1
    assert game.world.players[0].eliminated is True


def test_loss_enters_gameover_and_enter_starts_fresh_run(game):
    start_playing(game)
    game.world.apply_upgrade(0, "heavy_rounds")
    old_world = game.world
    game.world.status = "lost"

    game.update(1 / 60)

    assert game.state == "gameover"
    assert game.reason

    game.handle_event(key_event(config.CONFIRM_KEY))

    assert game.state == "playing"
    assert game.level_index == 0
    assert game.world is not old_world
    assert game.world.level_index == 0
    assert game.world.upgrade_levels == [{}, {}]
    assert game.world.player_stats[0].bullet_damage == (
        config.PlayerStats().bullet_damage
    )
    assert game.world.player_stats[1].max_hp == config.PlayerStats().max_hp


def test_boss_death_enters_victory(game):
    start_playing(game)
    game.level_index = config.BOSS_LEVEL
    game.world = World(
        config.BOSS_LEVEL,
        seed=1,
        player_stats=game.world.player_stats,
        upgrade_levels=game.world.upgrade_levels,
    )
    assert game.world.boss is not None
    game.world.boss.alive = False

    game.update(1 / 60)

    assert game.world.status == "victory"
    assert game.state == "victory"


def test_victory_enter_starts_fresh_run(game):
    start_playing(game)
    game.world.status = "victory"
    game.update(1 / 60)
    assert game.state == "victory"

    game.handle_event(key_event(config.CONFIRM_KEY))

    assert game.state == "playing"
    assert game.level_index == 0
    assert game.world.upgrade_levels == [{}, {}]
    assert all(
        stats.max_hp == config.PlayerStats().max_hp
        for stats in game.world.player_stats
    )


def test_intro_overlay_ticks_while_simulation_runs(game):
    start_playing(game)
    assert game.intro_timer == pytest.approx(1.2)
    before = game.world.elapsed

    game.update(0.05)

    assert game.world.elapsed > before
    assert 0.0 < game.intro_timer < 1.2

    for _ in range(30):
        game.update(0.05)

    assert game.intro_timer == 0.0


def test_update_and_draw_run_for_120_frames(game):
    start_playing(game)

    for _ in range(120):
        game.update(1 / 60)
        game.draw()


def test_game_draws_through_scaled_canvas():
    screen = pygame.Surface((800, 600))
    game = Game(screen, seed=11, audio=Audio(enabled=False))

    game.draw()

    assert screen.get_at((0, 0))[:3] == (0, 0, 0)
    assert any(
        screen.get_at((x, 300))[:3] != (0, 0, 0)
        for x in range(0, 800, 16)
    )


def test_skills_are_edge_triggered_on_keydown(game, monkeypatch):
    start_playing(game)
    pressed = {config.KEYMAP[0]["skill"]: True}
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: pressed)

    game.handle_event(key_event(config.KEYMAP[0]["skill"]))
    game.update(1 / 60)

    assert len(game.world.grenades) == 1

    game.update(1 / 60)

    assert len(game.world.grenades) == 1


def test_second_player_skill_fires_laser(game, monkeypatch):
    start_playing(game)
    pressed = {config.KEYMAP[1]["skill"]: True}
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: pressed)

    game.handle_event(key_event(config.KEYMAP[1]["skill"]))
    game.update(1 / 60)

    assert len(game.world.lasers) == 1


def test_audio_disabled_when_mixer_init_fails(monkeypatch):
    monkeypatch.setattr(pygame.mixer, "get_init", lambda: None)

    def fail() -> None:
        raise pygame.error("no audio device")

    monkeypatch.setattr(pygame.mixer, "init", fail)

    audio = Audio()

    assert audio.enabled is False
    assert audio.play("shoot") is None
    assert audio.toggle() is False


def test_audio_generates_all_named_sounds():
    audio = Audio()
    if not audio.enabled:
        pytest.skip("mixer unavailable")

    for name in (
        "shoot",
        "hit",
        "explosion",
        "laser",
        "pick",
        "lose",
        "win",
    ):
        audio.play(name)

    assert audio.toggle() is False
    assert audio.play("shoot") is None
    assert audio.toggle() is True
