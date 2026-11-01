import pygame
import pytest

import config
from game.enemies import make_enemy
from game.world import World


def test_stim_doubles_grenade_radius():
    world = World(0, seed=14)
    player = world.players[0]
    player.stim_timer = 10.0
    world.throw_grenade(player)
    assert world.grenades[-1].radius == pytest.approx(
        player.stats.grenade_radius * 2
    )


def test_stim_laser_fires_two_beams_and_hits_each_enemy_once():
    world = World(0, seed=15)
    player = world.players[1]
    player.stim_timer = 10.0
    player.direction = config.Direction.RIGHT
    tx, ty = world.point_to_tile(player.center)
    for x in range(tx + 1, tx + 4):
        world.grid[ty][x] = config.Tile.EMPTY
    enemy = make_enemy("tracker", (tx + 2, ty))
    enemy.hp = 100
    world.enemies.append(enemy)
    before_hp = enemy.hp
    assert world.fire_laser(player) is True
    assert len(world.lasers) == 2
    assert enemy.hp == before_hp - max(
        1, round(player.stats.laser_damage * 0.6)
    )


def test_twin_laser_does_not_double_hit_boss():
    world = World(config.BOSS_LEVEL, seed=16)
    player = world.players[1]
    player.stim_timer = 10.0
    player.pos = pygame.Vector2(
        world.boss.center.x, world.boss.center.y + 120
    )
    player.direction = config.Direction.UP
    before_hp = world.boss.hp
    world.fire_laser(player)
    assert world.boss.hp == before_hp - max(
        1, round(player.stats.laser_damage * 0.6)
    )


def test_twin_laser_uses_pre_fire_grid_for_bricks():
    world = World(0, seed=17)
    player = world.players[1]
    player.stim_timer = 10.0
    player.direction = config.Direction.UP
    tx, ty = world.point_to_tile(player.center)
    world.grid[ty - 1][tx] = config.Tile.EMPTY
    brick = (tx, ty - 2)
    world.grid[brick[1]][brick[0]] = config.Tile.BRICK
    world.fire_laser(player)
    assert world.grid[brick[1]][brick[0]] == config.Tile.EMPTY
