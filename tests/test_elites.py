import math

import pytest

import config
from game.world import World


@pytest.mark.parametrize("level_index", range(config.LEVEL_COUNT))
def test_every_level_has_planned_elites(level_index):
    world = World(level_index, seed=100 + level_index)
    assert world.elite_target_count == config.ELITE_COUNTS[level_index]


def test_early_quota_clear_spawns_pending_elites_immediately():
    world = World(2, seed=3)
    assert world.elite_spawned_count == 1
    world.quota_remaining = 0
    world._update_elite_spawning(0.0)
    assert world.elite_spawned_count == 2


def test_hell_elite_scales_only_with_elite_multiplier():
    world = World(3, seed=4, difficulty="hell")
    elite = next(e for e in world.enemies if e.kind == "elite")
    assert elite.max_hp == math.ceil((3 + 3 // 2) * 1.5)
    assert elite.shield == math.ceil((12 + 3) * 1.5)


def test_boss_level_elite_does_not_block_victory():
    world = World(config.BOSS_LEVEL, seed=5)
    assert world.elite_target_count == 1
    world.boss.alive = False
    world._on_boss_dead()
    assert world.status == "victory"


def test_elite_health_and_shield_grow_with_level_index():
    world = World(3, seed=6)
    elite = next(e for e in world.enemies if e.kind == "elite")
    assert elite.max_hp == config.ELITE_HP_BASE + 3 // 2
    assert elite.shield == config.ELITE_SHIELD_BASE + 3


def test_pending_elites_are_counted_as_remaining_enemies():
    world = World(2, seed=7)
    living = sum(1 for enemy in world.enemies if enemy.alive)
    pending = world.elite_target_count - world.elite_spawned_count
    assert pending == 1
    assert world.remaining_enemies == living + world.quota_remaining + pending


def test_pending_elites_wait_when_the_active_cap_is_reached():
    world = World(5, seed=8)
    world.quota_remaining = 0
    world._update_elite_spawning(0.0)
    assert world.elite_spawned_count == 2
    assert world._active_elite_count() == config.ELITE_MAX_ACTIVE
    before = world.elite_spawned_count
    world._update_elite_spawning(config.ELITE_RETRY_INTERVAL)
    assert world.elite_spawned_count == before
