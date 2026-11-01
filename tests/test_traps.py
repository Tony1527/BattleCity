import pytest

import config
from game.boss import Boss
from game.enemies import make_enemy
from game.hazards import Trap
from game.world import World


def test_trap_immobilizes_player_for_three_seconds():
    world = World(0, seed=7)
    trap = world.traps[0]
    player = world.players[0]
    player.pos = world.tile_center(*trap.tile)
    world._trigger_trap(player, (-1, -1))
    assert player.immobilized == pytest.approx(config.TRAP_DURATION)
    player.update_timers(2.9)
    assert player.can_shoot() is False
    assert world.throw_grenade(player) is False
    assert world.fire_laser(player) is False


def test_trap_does_not_retrigger_while_standing_on_it():
    world = World(0, seed=8)
    trap = world.traps[0]
    player = world.players[0]
    player.pos = world.tile_center(*trap.tile)
    world._trigger_trap(player, (-1, -1))
    player.immobilized = 0.0
    trap.cooldown = 0.0
    world._trigger_trap(player, trap.tile)
    assert player.immobilized == 0.0


def test_trap_affects_enemy_but_not_boss():
    world = World(0, seed=9)
    trap = world.traps[0]
    enemy = make_enemy("tracker", trap.tile)
    world.enemies.append(enemy)
    world._trigger_trap(enemy, (-1, -1))
    assert enemy.immobilized == pytest.approx(config.TRAP_DURATION)
    boss = Boss()
    assert not hasattr(boss, "immobilized")


def test_trap_rearms_after_cooldown_and_is_not_retriggered_early():
    trap = Trap((1, 1))

    assert trap.armed is True
    assert trap.try_trigger() is True
    assert trap.cooldown == pytest.approx(config.TRAP_REARM_TIME)
    assert trap.armed is False
    assert trap.try_trigger() is False

    trap.update(config.TRAP_REARM_TIME - 0.1)
    assert trap.armed is False
    assert trap.try_trigger() is False

    trap.update(0.1)
    assert trap.armed is True
    assert trap.try_trigger() is True


def test_immobilized_player_cannot_move():
    world = World(0, seed=10)
    player = world.players[0]
    player.immobilized = config.TRAP_DURATION
    start_x = player.pos.x

    moved = world.move_entity(player, config.Direction.RIGHT, 1.0)

    assert moved is False
    assert player.pos.x == pytest.approx(start_x)


@pytest.mark.parametrize("level_index", range(config.LEVEL_COUNT))
def test_trap_placement_respects_level_constraints(level_index):
    world = World(level_index, seed=500 + level_index)
    level_traps = world.level.traps

    assert len(level_traps) == config.TRAP_COUNTS[level_index]
    assert set(level_traps) == {trap.tile for trap in world.traps}

    for tx, ty in level_traps:
        assert world.grid[ty][tx] == config.Tile.EMPTY
        assert not any(
            abs(tx - bx) <= 2 and abs(ty - by) <= 2
            for bx, by in config.BASE_TILES
        )
        assert not (6 <= tx <= 17 and 1 <= ty <= 4)
        for sx, sy in (*config.ENEMY_SPAWNS, *config.PLAYER_SPAWNS):
            assert max(abs(tx - sx), abs(ty - sy)) > config.SPAWN_SAFE_RADIUS
        assert any(
            world.find_path(spawn, (tx, ty)) is not None
            for spawn in config.PLAYER_SPAWNS
        )
