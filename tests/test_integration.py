from __future__ import annotations

from pathlib import Path

import pygame
import pytest

import config
from game.audio import Audio
from game.enemies import make_enemy
from game.geometry import tile_center
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

        assert world.elite_target_count == config.ELITE_COUNTS[level_index]
        assert world.elite_spawned_count == 1
        assert any(
            enemy.kind == "elite" and enemy.alive
            for enemy in world.enemies
        )

        if level_index == config.BOSS_LEVEL:
            assert world.boss is not None
            assert world.boss.hp == config.BOSS_HP
            assert world.quota_remaining == 0
            assert world.spawn_quota == 0
        else:
            assert world.boss is None
            assert world.quota_remaining == config.ENEMY_QUOTA[level_index]
            assert world.spawn_quota == config.ENEMY_QUOTA[level_index]

        inputs = [PlayerInput() for _ in world.players]
        for _ in range(120):
            world.update(1 / 60, inputs)

        assert world.elapsed == pytest.approx(2.0)


def test_full_run_normal_and_hell_construct_all_levels() -> None:
    for mode in ("normal", "hell"):
        for level_index in range(config.LEVEL_COUNT):
            world = World(
                level_index, seed=3000 + level_index, difficulty=mode
            )

            assert world.difficulty.key == mode
            assert world.base.max_hp == (
                config.BASE_HP_HELL
                if mode == "hell"
                else config.BASE_HP_NORMAL
            )
            assert validate_level(world.level)
            assert (
                world.elite_target_count == config.ELITE_COUNTS[level_index]
            )
            assert len(world.traps) == config.TRAP_COUNTS[level_index]

            for _ in range(120):
                world.update(
                    1 / 60, [PlayerInput() for _ in world.players]
                )

            assert world.elapsed == pytest.approx(2.0)


def test_retry_flow_and_language_switch(game: Game) -> None:
    start_playing(game)
    old_world = game.world

    game.world.status = "lost"
    game.update(1 / 60)
    assert game.state == "gameover"

    game.handle_event(key_event(config.CONFIRM_KEY))
    assert game.state == "playing"
    assert game.level_index == 0
    assert game.world is not old_world
    assert game.world.level_index == 0

    game.handle_event(key_event(config.PAUSE_KEY))
    assert game.state == "paused"

    before = game.language
    game.handle_event(key_event(pygame.K_l))
    assert game.language != before
    assert game.renderer.language == game.language


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


def combat_world(level: int, seed: int = 77) -> World:
    world = World(level, seed=seed)
    world.grid = [
        [config.Tile.EMPTY for _ in range(config.GRID_COLS)]
        for _ in range(config.GRID_ROWS)
    ]
    world.level.grid = world.grid
    world.quota_remaining = 0
    world.spawn_quota = 0
    world.spawn_timer = float("inf")
    world.max_active = 0
    world.base.reset_for_level(shield=1000)
    return world


def test_scripted_bullet_and_grenade_and_laser_kill_a_normal_enemy():
    stats = config.PlayerStats(bullet_damage=2)
    world = combat_world(0)
    world.player_stats[0] = stats
    player = world.players[0]
    player.stats = stats
    player.pos = tile_center(5, 5)
    player.direction = config.Direction.RIGHT
    enemy = make_enemy("tracker", (6, 5))
    world.enemies = [enemy]
    inputs = [PlayerInput(shoot=True), PlayerInput()]

    for _ in range(120):
        world.update(1 / 60, inputs)
        if not enemy.alive:
            break

    assert not enemy.alive

    grenade_world = combat_world(0)
    thrower = grenade_world.players[0]
    thrower.pos = tile_center(5, 5)
    thrower.direction = config.Direction.RIGHT
    doomed = make_enemy("tracker", (10, 5))
    grenade_world.enemies = [doomed]

    assert grenade_world.throw_grenade(thrower)
    grenade_world.update(config.GRENADE_FLIGHT + 0.01, [])

    assert not doomed.alive

    laser_world = combat_world(0)
    shooter = laser_world.players[0]
    shooter.pos = tile_center(5, 5)
    shooter.direction = config.Direction.RIGHT
    target = make_enemy("tracker", (7, 5))
    laser_world.enemies = [target]

    assert laser_world.fire_laser(shooter)
    laser_world.update(0.0, [])

    assert not target.alive


def test_scripted_laser_damages_the_boss_through_world_updates():
    world = combat_world(config.BOSS_LEVEL)
    boss = world.boss
    assert boss is not None
    player = world.players[0]
    player.pos = pygame.Vector2(
        boss.center.x + 30, tile_center(12, 5).y
    )
    player.direction = config.Direction.UP
    start_hp = boss.hp

    assert world.fire_laser(player)
    world.update(0.0, [])

    assert boss.hp == start_hp - player.stats.laser_damage
    assert boss.hp < boss.max_hp


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
        "7 个普通关",
        "每关都会出现精英敌人",
        "1 个 Boss 关",
        "最终 Boss",
        "跳过该关升级",
        "## 难度",
        "## 关卡与敌人",
        "## 地形、陷阱与补给",
        "## 语言",
        "## 失败与重试",
        "## 字体与许可",
        "地狱",
        "精英数量",
        "按 `L`",
        "重试当前关卡",
        "河流",
        "桥",
        "陷阱",
        "维修",
        "强化",
        "无敌",
        "NotoSansSC-Regular-subset.otf",
        "assets/fonts/OFL.txt",
        "SIL Open Font License 1.1",
    ):
        assert token in readme
