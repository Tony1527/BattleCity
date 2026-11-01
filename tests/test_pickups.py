import pytest

import config
from game.pickups import Pickup, roll_pickup_kind
from game.world import World


def test_repair_heals_one_and_is_not_consumed_at_full_hp():
    world = World(0, seed=10)
    player = world.players[0]
    player.hp = player.max_hp - 1
    pickup = Pickup("repair", player.center)
    assert world._apply_pickup(player, pickup) is True
    assert player.hp == player.max_hp

    pickup = Pickup("repair", player.center)
    assert world._apply_pickup(player, pickup) is False
    assert pickup.ttl == pytest.approx(config.ITEM_TTL)


def test_stim_sets_twenty_second_timer_and_does_not_stack():
    world = World(0, seed=11)
    player = world.players[0]
    player.stim_timer = 12.0
    world._apply_pickup(player, Pickup("stim", player.center))
    assert player.stim_timer == pytest.approx(20.0)


def test_invincibility_blocks_damage_for_six_seconds():
    world = World(0, seed=12)
    player = world.players[0]
    world._apply_pickup(player, Pickup("invincible", player.center))
    assert player.invincible_timer == pytest.approx(6.0)
    world.damage_player(player, player.max_hp)
    assert player.alive is True


def test_pickups_respect_map_cap_and_ttl():
    world = World(0, seed=13)
    world.pickups = [Pickup("repair", world.tile_center(3, 5)) for _ in range(2)]
    world._update_pickups(100.0)
    assert len(world.pickups) <= 2


def test_pickup_update_reports_whether_it_survives():
    pickup = Pickup("stim", (0.0, 0.0))
    assert pickup.update(config.ITEM_TTL - 0.1) is True
    assert pickup.update(0.2) is False
    assert pickup.ttl == pytest.approx(0.0)


def test_roll_pickup_kind_only_returns_known_kinds():
    import random

    rng = random.Random(1234)
    kinds = {roll_pickup_kind(rng) for _ in range(200)}
    assert kinds
    assert kinds <= set(config.ITEM_WEIGHTS)


def test_invincible_timer_expires_and_damage_applies_again():
    world = World(0, seed=14)
    player = world.players[0]
    world._apply_pickup(player, Pickup("invincible", player.center))
    player.update_timers(6.0)
    assert player.invincible_timer == pytest.approx(0.0)
    world.damage_player(player, 1)
    assert player.hp == player.max_hp - 1


def test_spawned_pickups_use_reachable_empty_tiles():
    world = World(2, seed=15)
    world._update_pickups(config.ITEM_INITIAL_DELAY)
    assert len(world.pickups) <= config.ITEM_MAX_ON_MAP
    protected = set(config.BASE_TILES) | set(config.BASE_ENTRANCES)
    trap_tiles = {trap.tile for trap in world.traps}
    for pickup in world.pickups:
        tx, ty = world.point_to_tile(pickup.pos)
        assert world.grid[ty][tx] == config.Tile.EMPTY
        assert (tx, ty) not in protected
        assert (tx, ty) not in trap_tiles
        for sx, sy in (*config.ENEMY_SPAWNS, *config.PLAYER_SPAWNS):
            assert max(abs(tx - sx), abs(ty - sy)) > config.SPAWN_SAFE_RADIUS
        assert any(
            world.find_path(spawn, (tx, ty)) is not None
            for spawn in config.PLAYER_SPAWNS
        )


def test_pickup_rng_is_independent_from_enemy_rng():
    world = World(0, seed=16)
    world.pickups = []
    world.pickup_timer = 0.0
    world._update_pickups(0.0)
    assert world.random.getstate() == World(0, seed=16).random.getstate()
