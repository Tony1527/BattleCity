from dataclasses import FrozenInstanceError, fields

import pygame
import pytest

import config


def test_layout_constants():
    assert config.SCREEN_WIDTH == 1280
    assert config.SCREEN_HEIGHT == 720
    assert config.FPS == 60
    assert config.TILE == 48
    assert (config.GRID_COLS, config.GRID_ROWS) == (24, 13)
    assert config.PLAYFIELD_X == 64
    assert config.PLAYFIELD_Y == 0
    assert config.HUD_Y == 624


def test_base_tiles_are_bottom_center_2x2():
    assert set(config.BASE_TILES) == {
        (11, 11),
        (12, 11),
        (11, 12),
        (12, 12),
    }


def test_base_entrances_touch_base_from_multiple_directions():
    base = set(config.BASE_TILES)
    assert set(config.BASE_ENTRANCES).isdisjoint(base)
    assert len(set(config.BASE_ENTRANCES)) == len(config.BASE_ENTRANCES)
    directions = {
        (
            (0 if tx == 11 or tx == 12 else (1 if tx > 12 else -1)),
            (-1 if ty < 11 else (1 if ty > 12 else 0)),
        )
        for tx, ty in config.BASE_ENTRANCES
    }
    assert len(directions) >= 2


def test_spawns_and_level_progression_constants():
    assert len(config.ENEMY_SPAWNS) == 3
    assert len(set(config.ENEMY_SPAWNS)) == 3
    assert len(config.PLAYER_SPAWNS) == 2
    assert len(set(config.PLAYER_SPAWNS)) == 2
    for tx, ty in (*config.ENEMY_SPAWNS, *config.PLAYER_SPAWNS):
        assert 0 <= tx < config.GRID_COLS
        assert 0 <= ty < config.GRID_ROWS
    assert config.LEVEL_COUNT == 8
    assert config.BOSS_LEVEL == 7
    assert config.ELITE_COUNTS == (1, 1, 2, 2, 2, 3, 3, 1)
    assert len(config.ELITE_COUNTS) == config.LEVEL_COUNT
    assert len(config.ENEMY_QUOTA) == config.LEVEL_COUNT
    assert len(config.MAX_ACTIVE_ENEMIES) == config.LEVEL_COUNT
    assert len(config.SPAWN_INTERVAL) == config.LEVEL_COUNT
    assert config.ENEMY_QUOTA[config.BOSS_LEVEL] == 0


def test_difficulty_and_spawn_constants_match_spec():
    assert config.SPAWN_INTERVAL == (
        4.8,
        4.4,
        4.0,
        3.6,
        3.2,
        2.8,
        2.4,
        0.0,
    )
    assert config.BASE_HP_NORMAL == 3
    assert config.BASE_HP_HELL == 6
    assert config.ELITE_SPAWN_INTERVAL == 22.0
    assert config.ELITE_RETRY_INTERVAL == 2.0
    assert config.ELITE_MAX_ACTIVE == 2
    assert config.ELITE_HP_BASE == 3
    assert config.ELITE_SHIELD_BASE == 12
    assert config.ELITE_SUMMON_INTERVAL == 10.0
    assert config.ELITE_MAX_SUMMONS == 1


def test_player_stats_defaults_match_spec():
    stats = config.PlayerStats()
    assert stats.max_hp == 3
    assert stats.speed == 150.0
    assert stats.fire_interval == 0.35
    assert stats.bullet_damage == 1
    assert stats.bullet_speed == 400.0
    assert stats.damage_reduction == 0.0
    assert stats.grenade_cooldown == 6.0
    assert stats.grenade_damage == 40
    assert stats.grenade_radius == 72.0
    assert stats.laser_cooldown == 5.0
    assert stats.laser_damage == 60
    assert stats.laser_range == 384.0
    assert stats.extra_lives == 0
    assert stats.base_shield == 0
    assert stats.grenade_split == 0
    assert stats.laser_reflect == 0


def test_player_stats_field_order_and_clone():
    expected = [
        "max_hp",
        "speed",
        "fire_interval",
        "bullet_damage",
        "bullet_speed",
        "damage_reduction",
        "grenade_cooldown",
        "grenade_damage",
        "grenade_radius",
        "laser_cooldown",
        "laser_damage",
        "laser_range",
        "extra_lives",
        "base_shield",
        "grenade_split",
        "laser_reflect",
    ]
    assert [f.name for f in fields(config.PlayerStats)] == expected

    stats = config.PlayerStats()
    clone = stats.clone()
    assert clone == stats
    assert clone is not stats
    clone.max_hp = 99
    assert stats.max_hp == 3


def test_enemy_specs_match_plan():
    tracker = config.ENEMY_SPECS["tracker"]
    gunner = config.ENEMY_SPECS["gunner"]
    demolisher = config.ENEMY_SPECS["demolisher"]
    assert tracker == config.EnemySpec("tracker", 2, 78, 1.5, 230, 1, 5 * 48, 10)
    assert gunner == config.EnemySpec("gunner", 3, 60, 1.9, 300, 1, 8 * 48, 15)
    assert demolisher == config.EnemySpec("demolisher", 4, 95, 2.5, 0, 0, 1.5 * 48, 20)
    with pytest.raises(FrozenInstanceError):
        tracker.hp = 100


def test_direction_vectors_are_orthogonal_unit_vectors():
    for direction in config.Direction:
        dx, dy = direction.vector
        assert dx * dy == 0
        assert abs(dx) + abs(dy) == 1
        assert config.Direction.from_vector(dx, dy) is direction
        assert direction.angle in (0.0, 90.0, 180.0, 270.0)
    assert config.Direction.from_vector(0, -1) is config.Direction.UP
    assert config.Direction.UP.angle == 0.0
    assert config.Direction.RIGHT.angle == 90.0
    assert config.Direction.DOWN.angle == 180.0
    assert config.Direction.LEFT.angle == 270.0


def test_tiles_are_int_enum():
    assert config.Tile.EMPTY.value == 0
    assert config.Tile.BRICK.value == 1
    assert config.Tile.STEEL.value == 2
    assert config.Tile.RIVER.value == 3
    assert config.Tile.BRIDGE.value == 4


def test_river_and_bridge_constants_match_spec():
    assert config.RIVER_BANDS == (0, 1, 1, 1, 2, 2, 2, 0)
    assert len(config.RIVER_BANDS) == config.LEVEL_COUNT
    assert config.BRIDGE_COUNT == 3
    assert config.BRIDGE_WIDTH == 2


def test_keymap_defaults():
    assert config.KEYMAP[0]["skill"] == pygame.K_f
    assert config.KEYMAP[0]["shoot"] == pygame.K_SPACE
    assert config.KEYMAP[1]["skill"] == pygame.K_SLASH
    assert config.KEYMAP[1]["shoot"] == pygame.K_PERIOD
    for player_keys in config.KEYMAP:
        assert set(player_keys) >= {"up", "down", "left", "right", "shoot", "skill"}


def test_colors_are_rgb_tuples():
    names = (
        "BG",
        "FLOOR",
        "GRID",
        "STEEL",
        "BRICK",
        "P1_BLUE",
        "P2_AMBER",
        "ENEMY_RED",
        "ENEMY_ORANGE",
        "HOLO_WHITE",
    )
    for name in names:
        color = getattr(config, name)
        assert len(color) == 3
        assert all(isinstance(channel, int) and 0 <= channel <= 255 for channel in color)
