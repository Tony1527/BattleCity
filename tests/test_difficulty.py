import math

import pytest

import config
from game import difficulty
from game.world import World


def test_profiles_match_spec():
    normal = difficulty.get_profile("normal")
    hell = difficulty.get_profile("hell")
    assert normal.base_hp == 3
    assert hell.base_hp == 6
    assert hell.enemy_hp_mult == 1.5
    assert hell.enemy_fire_interval_mult == 0.8
    assert hell.enemy_attack_range_mult == 1.15
    assert hell.spawn_interval_mult == 0.8
    assert hell.boss_hp_mult == 1.5
    assert hell.boss_interval_mult == 0.85


def test_hell_scales_normal_enemy_once():
    spec = difficulty.scaled_enemy_spec(
        "tracker", difficulty.get_profile("hell")
    )
    assert spec.hp == 3
    assert spec.fire_interval == pytest.approx(1.2)
    assert spec.attack_range == pytest.approx(276.0)


def test_scaling_does_not_mutate_global_enemy_templates():
    before = config.ENEMY_SPECS["tracker"]
    difficulty.scaled_enemy_spec("tracker", difficulty.get_profile("hell"))
    assert config.ENEMY_SPECS["tracker"] is before
    assert config.ENEMY_SPECS["tracker"].hp == 2
    assert config.ENEMY_SPECS["tracker"].fire_interval == pytest.approx(1.5)
    assert config.ENEMY_SPECS["tracker"].attack_range == pytest.approx(240.0)


def test_world_uses_difficulty_for_base_and_spawn_interval():
    normal = World(0, seed=1, difficulty="normal")
    hell = World(0, seed=1, difficulty="hell")
    assert normal.base.max_hp == 3
    assert hell.base.max_hp == 6
    assert hell._spawn_interval() == pytest.approx(
        normal._spawn_interval() * 0.8
    )


def test_world_defaults_to_normal_difficulty():
    world = World(0, seed=1)
    assert world.difficulty is difficulty.get_profile("normal")
    assert world.base.max_hp == config.BASE_HP_NORMAL


def test_hell_world_spawns_scaled_normal_enemies():
    world = World(0, seed=1, difficulty="hell")
    enemy = world.spawn_enemy("tracker", None)

    assert enemy is not None
    assert enemy.spec is not config.ENEMY_SPECS["tracker"]
    assert enemy.max_hp == 3
    assert enemy.hp == 3
    assert enemy.spec.fire_interval == pytest.approx(1.2)
    assert enemy.spec.attack_range == pytest.approx(276.0)


def test_world_boss_uses_difficulty_multipliers():
    world = World(config.BOSS_LEVEL, seed=1, difficulty="hell")

    assert world.boss.max_hp == math.ceil(config.BOSS_HP * 1.5)
    assert world.boss.aim_timer == pytest.approx(
        config.BOSS_AIM_INTERVAL[0] * 0.85
    )
    assert world.boss.interval_mult == pytest.approx(0.85)
