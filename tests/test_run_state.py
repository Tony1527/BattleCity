from __future__ import annotations

import pygame
import pytest

import config
from game.audio import Audio
from game.run import RunState
from game.states import Game


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


def test_player_elimination_retry_preserves_upgrades_lives_and_base(game):
    start_playing(game)
    game.world.apply_upgrade(0, "heavy_rounds")
    game.world.shared_lives = 0
    game.world.base.hp = 1
    game.world.base.shield = 2
    game.world.players[0].eliminated = True
    game.world.players[1].eliminated = True
    game.update(1 / 60)
    assert game.state == "gameover"
    assert game.reason == "gameover.both_eliminated"

    game.handle_event(key_event(config.CONFIRM_KEY))

    assert game.state == "playing"
    assert game.level_index == 0
    assert game.world.upgrade_levels[0]["heavy_rounds"] == 1
    assert game.world.shared_lives == 0
    assert game.world.base.hp == 1
    assert game.world.base.shield == 2
    assert all(p.alive and not p.eliminated for p in game.world.players)


def test_base_destroyed_retry_restores_full_base(game):
    start_playing(game)
    game.world.base.hp = 0
    game.world.base.alive = False
    game.update(1 / 60)
    assert game.state == "gameover"
    assert game.reason == "gameover.base_destroyed"
    game.handle_event(key_event(config.CONFIRM_KEY))

    assert game.world.base.alive is True
    assert game.world.base.hp == game.world.base.max_hp
    assert game.world.level_index == 0


def test_gameover_escape_returns_to_title(game):
    start_playing(game)
    game.world.status = "lost"
    game.update(1 / 60)
    game.handle_event(key_event(config.PAUSE_KEY))
    assert game.state == "title"


def test_capture_run_state_records_progression(game):
    start_playing(game)
    game.world.apply_upgrade(0, "heavy_rounds")
    game.world.shared_lives = 2

    state = game._capture_run_state()

    assert isinstance(state, RunState)
    assert state.run_seed == game._run_seed
    assert state.difficulty == "normal"
    assert state.language == "zh"
    assert state.level_index == 0
    assert state.upgrade_levels[0]["heavy_rounds"] == 1
    assert state.shared_lives == 2
    assert state.player_stats[0].bullet_damage == 2


def test_retry_rebuilds_same_level_with_same_seed(game):
    start_playing(game)
    old_seed = game.world.seed
    old_grid = [row[:] for row in game.world.grid]
    game.world.status = "lost"
    game.update(1 / 60)

    game.handle_event(key_event(config.CONFIRM_KEY))

    assert game.world.seed == old_seed
    assert game.world.grid == old_grid


def test_title_right_selects_hell_and_starts_hell_run(game):
    game.handle_event(key_event(pygame.K_RIGHT))

    assert game.difficulty == "hell"

    start_playing(game)

    assert game.world.difficulty.key == "hell"
    assert game.world.base.max_hp == config.BASE_HP_HELL


def test_retry_at_level_above_zero_rebuilds_the_same_level(game):
    start_playing(game)
    game.level_index = 3
    game.world = game._make_world(
        3, game.world.player_stats, game.world.upgrade_levels
    )
    old_seed = game.world.seed
    game.world.status = "lost"
    game.update(1 / 60)
    assert game.state == "gameover"

    game.handle_event(key_event(config.CONFIRM_KEY))

    assert game.state == "playing"
    assert game.level_index == 3
    assert game.world.level_index == 3
    assert game.world.seed == old_seed
