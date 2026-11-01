from __future__ import annotations

from pathlib import Path

import pygame
import pytest

import config
from game.audio import Audio
from game.input import PlayerInput
from game.levelgen import validate_level
from game.states import Game
from game.world import World

ROOT = Path(__file__).resolve().parents[1]


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


def test_game_runs_120_update_and_draw_frames(game: Game) -> None:
    start_playing(game)

    for _ in range(120):
        game.update(1 / 60)
        game.draw()

    assert game.world.elapsed > 0.0
    assert game.running is True


def test_all_eight_levels_construct_validate_and_update() -> None:
    for level_index in range(config.LEVEL_COUNT):
        world = World(level_index, seed=1000 + level_index)

        assert world.level_index == level_index
        assert validate_level(world.level)
        assert len(world.grid) == config.GRID_ROWS
        assert all(len(row) == config.GRID_COLS for row in world.grid)

        if level_index == config.BOSS_LEVEL:
            assert world.boss is not None
            assert world.boss.hp == config.BOSS_HP
            assert world.quota_remaining == 0
            assert world.spawn_quota == 0
            assert world.elite_spawned is False
        else:
            assert world.boss is None
            assert world.quota_remaining == config.ENEMY_QUOTA[level_index]
            assert world.spawn_quota == config.ENEMY_QUOTA[level_index]
            if level_index in config.ELITE_LEVELS:
                assert world.elite_spawned is True
                assert any(
                    enemy.kind == "elite" and enemy.alive
                    for enemy in world.enemies
                )
            else:
                assert world.elite_spawned is False
                assert not any(
                    enemy.kind == "elite" for enemy in world.enemies
                )

        inputs = [PlayerInput() for _ in world.players]
        for _ in range(120):
            world.update(1 / 60, inputs)

        assert world.elapsed == pytest.approx(2.0)


def test_full_transition_from_title_to_boss_victory(game: Game) -> None:
    assert game.state == "title"

    game.handle_event(key_event(config.CONFIRM_KEY))
    assert game.state == "controls"

    game.handle_event(key_event(config.CONFIRM_KEY))
    assert game.state == "playing"
    assert game.level_index == 0

    for level_index in range(config.BOSS_LEVEL):
        assert game.level_index == level_index
        assert game.world.level_index == level_index
        assert game.world.status == "playing"

        game.world.status = "cleared"
        game.update(1 / 60)

        assert game.state == "upgrade"
        assert len(game.offers[0]) == 3
        assert len(game.offers[1]) == 3

        choices = 0
        while game.state == "upgrade":
            game.handle_event(key_event(config.CHOICE_KEYS[0]))
            choices += 1
            assert choices <= len(game.world.players)

        assert game.state == "playing"
        assert game.level_index == level_index + 1
        assert game.world.level_index == level_index + 1

    assert game.level_index == config.BOSS_LEVEL
    assert game.world.boss is not None
    assert game.world.boss.alive is True

    game.world.boss.alive = False
    game.update(1 / 60)

    assert game.world.status == "victory"
    assert game.state == "victory"
    assert game.level_index == config.BOSS_LEVEL

    game.draw()


def test_pause_clears_pending_skill_latch(
    game: Game, monkeypatch: pytest.MonkeyPatch
) -> None:
    start_playing(game)
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: {})

    game.handle_event(key_event(config.KEYMAP[0]["skill"]))
    game.handle_event(key_event(config.PAUSE_KEY))
    assert game.state == "paused"

    game.handle_event(key_event(config.PAUSE_KEY))
    assert game.state == "playing"

    game.update(1 / 60)

    assert game.world.grenades == []


def test_requirements_and_readme_document_the_workflow() -> None:
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    lines = [
        line.strip().lower()
        for line in requirements.splitlines()
        if line.strip()
    ]
    assert any(line.startswith("pygame-ce") for line in lines)
    assert any(line.startswith("pytest") for line in lines)

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for token in (
        "python3 -m venv .venv",
        ".venv/bin/pip install -r requirements.txt",
        ".venv/bin/python main.py",
        ".venv/bin/pytest",
        "WASD",
        "Space",
        "F",
        "方向键",
        "`.`",
        "`/`",
        "Esc",
        "Enter",
        "docs/superpowers/specs/2026-10-31-battlecity-design.md",
        "docs/superpowers/plans/2026-10-31-battlecity.md",
        "不依赖任何外部图片或音频素材",
        "3 个普通关",
        "2 个普通关",
        "5 个普通关",
        "精英关 1",
        "精英关 2",
        "最终 Boss",
        "跳过该关升级",
    ):
        assert token in readme
