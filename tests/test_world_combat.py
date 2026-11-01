import pygame
import pytest

import config
from game.enemies import make_enemy
from game.geometry import tile_center
from game.skills import Grenade, LaserBeam
from game.world import World


def empty_grid():
    return [
        [config.Tile.EMPTY for _ in range(config.GRID_COLS)]
        for _ in range(config.GRID_ROWS)
    ]


def open_world(seed=1, player_stats=None):
    world = World(0, seed=seed, player_stats=player_stats)
    world.grid = empty_grid()
    world.level.grid = world.grid
    return world


def test_throw_grenade_creates_grenade_toward_facing_and_sets_cooldown():
    world = open_world()
    player = world.players[0]
    player.pos = tile_center(5, 5)
    player.direction = config.Direction.RIGHT

    assert world.throw_grenade(player)

    assert len(world.grenades) == 1
    grenade = world.grenades[0]
    assert isinstance(grenade, Grenade)
    assert grenade.owner_id == player.player_id
    assert grenade.direction == config.Direction.RIGHT
    assert grenade.start == player.center
    assert grenade.damage == player.stats.grenade_damage
    assert grenade.radius == player.stats.grenade_radius
    assert grenade.split == player.stats.grenade_split
    assert player.grenade_timer == pytest.approx(
        player.stats.grenade_cooldown
    )
    assert world.effects.particles != []

    assert not world.throw_grenade(player)
    assert len(world.grenades) == 1


def test_grenade_damages_enemies_fully_players_at_thirty_five_percent_and_never_base():
    world = open_world()
    thrower, ally = world.players
    target = pygame.Vector2(world.base.center)

    thrower.pos = target
    thrower.invuln = 0.0
    thrower.hp = 50
    ally.pos = target + pygame.Vector2(0, 20)
    ally.invuln = 0.0
    ally.hp = 50

    enemy = make_enemy("tracker", (5, 5))
    enemy.pos = target + pygame.Vector2(0, -20)
    enemy.hp = 100
    world.enemies.append(enemy)

    grenade = Grenade(
        target, config.Direction.RIGHT, owner_id=0, damage=40
    )
    grenade.target = pygame.Vector2(target)

    world.resolve_grenade(grenade)

    player_damage = round(40 * config.GRENADE_FRIENDLY_FACTOR)
    assert enemy.hp == 100 - 40
    assert thrower.hp == 50 - player_damage
    assert ally.hp == 50 - player_damage
    assert world.base.hp == config.BASE_HP
    assert world.base.alive


def test_grenade_destroys_bricks_inside_radius_but_not_outside_or_steel():
    world = open_world()
    target = tile_center(5, 5)
    world.grid[5][5] = config.Tile.BRICK
    world.grid[4][5] = config.Tile.BRICK
    world.grid[5][7] = config.Tile.BRICK
    world.grid[5][6] = config.Tile.STEEL

    grenade = Grenade(target, config.Direction.RIGHT)
    grenade.target = pygame.Vector2(target)

    world.resolve_grenade(grenade)

    assert not world.is_brick(5, 5)
    assert not world.is_brick(5, 4)
    assert world.is_brick(7, 5)
    assert world.is_steel(6, 5)


def test_grenade_landing_on_steel_still_explodes_and_destroys_nearby_bricks():
    world = open_world()
    player = world.players[0]
    player.pos = tile_center(2, 5)
    player.direction = config.Direction.RIGHT
    world.grid[5][7] = config.Tile.STEEL
    world.grid[4][7] = config.Tile.BRICK

    assert world.throw_grenade(player)
    world.update(config.GRENADE_FLIGHT, [])

    assert world.grenades == []
    assert world.is_steel(7, 5)
    assert not world.is_brick(7, 4)


def test_grenade_split_creates_the_configured_number_of_explosions():
    world = open_world()
    target = tile_center(5, 5)
    grenade = Grenade(
        target,
        config.Direction.RIGHT,
        damage=40,
        radius=40.0,
        split=2,
    )
    grenade.target = pygame.Vector2(target)

    plus = make_enemy("tracker", (5, 5))
    plus.pos = target + pygame.Vector2(0, 60)
    plus.hp = 100
    minus = make_enemy("tracker", (5, 5))
    minus.pos = target + pygame.Vector2(0, -60)
    minus.hp = 100
    world.enemies = [plus, minus]

    world.resolve_grenade(grenade)

    assert plus.hp == 60
    assert minus.hp == 60


def test_fire_laser_damages_every_enemy_but_not_players_or_base():
    world = open_world()
    player = world.players[0]
    player.pos = tile_center(2, 5)
    player.direction = config.Direction.RIGHT

    near = make_enemy("tracker", (4, 5))
    near.pos = tile_center(4, 5)
    near.hp = 100
    far = make_enemy("gunner", (8, 5))
    far.pos = tile_center(8, 5)
    far.hp = 100
    world.enemies = [near, far]

    ally = world.players[1]
    ally.pos = tile_center(6, 5)
    ally.invuln = 0.0
    ally.hp = 50

    assert world.fire_laser(player)

    assert len(world.lasers) == 1
    assert isinstance(world.lasers[0], LaserBeam)
    assert near.hp == 100 - player.stats.laser_damage
    assert far.hp == 100 - player.stats.laser_damage
    assert ally.hp == 50
    assert world.base.hp == config.BASE_HP
    assert player.laser_timer == pytest.approx(
        player.stats.laser_cooldown
    )

    assert not world.fire_laser(player)


def test_laser_destroys_exactly_the_first_brick_and_stops():
    world = open_world()
    player = world.players[0]
    player.pos = tile_center(2, 5)
    player.direction = config.Direction.RIGHT
    world.grid[5][5] = config.Tile.BRICK
    world.grid[5][7] = config.Tile.BRICK

    before = make_enemy("tracker", (4, 5))
    before.pos = tile_center(4, 5)
    before.hp = 100
    beyond = make_enemy("tracker", (6, 5))
    beyond.pos = tile_center(6, 5)
    beyond.hp = 100
    world.enemies = [before, beyond]

    assert world.fire_laser(player)

    beam = world.lasers[0]
    assert beam.brick_tile == (5, 5)
    assert not world.is_brick(5, 5)
    assert world.is_brick(7, 5)
    assert before.hp == 100 - player.stats.laser_damage
    assert beyond.hp == 100


def test_laser_is_blocked_by_steel_without_destroying_bricks_beyond():
    world = open_world()
    player = world.players[0]
    player.pos = tile_center(2, 5)
    player.direction = config.Direction.RIGHT
    world.grid[5][5] = config.Tile.STEEL
    world.grid[5][7] = config.Tile.BRICK

    enemy = make_enemy("tracker", (7, 5))
    enemy.pos = tile_center(7, 5)
    enemy.hp = 100
    world.enemies.append(enemy)

    assert world.fire_laser(player)

    assert world.lasers[0].brick_tile is None
    assert world.is_steel(5, 5)
    assert world.is_brick(7, 5)
    assert enemy.hp == 100


def test_laser_range_respects_player_stats():
    stats = config.PlayerStats(laser_range=2 * config.TILE)
    world = open_world(player_stats=[stats])
    player = world.players[0]
    player.pos = tile_center(2, 5)
    player.direction = config.Direction.RIGHT

    inside = make_enemy("tracker", (4, 5))
    inside.pos = tile_center(4, 5)
    inside.hp = 100
    outside = make_enemy("tracker", (6, 5))
    outside.pos = tile_center(6, 5)
    outside.hp = 100
    world.enemies = [inside, outside]

    assert world.fire_laser(player)

    beam = world.lasers[0]
    assert beam.length == pytest.approx(2 * config.TILE)
    assert inside.hp == 100 - player.stats.laser_damage
    assert outside.hp == 100


def test_skill_cooldowns_prevent_immediate_reuse_and_tick_down():
    world = open_world()
    player = world.players[0]

    assert world.throw_grenade(player)
    assert world.fire_laser(player)
    assert not world.throw_grenade(player)
    assert not world.fire_laser(player)

    world.update(2.0, [])

    assert player.grenade_timer == pytest.approx(
        player.stats.grenade_cooldown - 2.0
    )
    assert player.laser_timer == pytest.approx(
        player.stats.laser_cooldown - 2.0
    )
    assert not world.throw_grenade(player)
    assert not world.fire_laser(player)

    world.update(max(player.stats.grenade_cooldown, player.stats.laser_cooldown), [])

    assert player.grenade_timer == 0.0
    assert player.laser_timer == 0.0
    assert world.throw_grenade(player)
    assert world.fire_laser(player)


def test_lasers_expire_after_laser_life():
    world = open_world()
    player = world.players[0]

    assert world.fire_laser(player)
    assert len(world.lasers) == 1

    world.update(config.LASER_LIFE + 0.001, [])

    assert world.lasers == []


def test_apply_upgrade_updates_live_stats_and_heals_by_max_hp_delta():
    world = open_world()
    player = world.players[0]
    player.hp = 1

    assert world.apply_upgrade(0, "plated_hull")

    assert player.stats.max_hp == config.PlayerStats().max_hp + 1
    assert player.max_hp == player.stats.max_hp
    assert player.hp == 2
    assert world.player_stats[0] is player.stats
    assert world.upgrade_levels[0]["plated_hull"] == 1
    assert world.players[1].stats.max_hp == config.PlayerStats().max_hp


def test_apply_upgrade_updates_non_hp_stats_and_rejects_capped_upgrades():
    world = open_world()
    player = world.players[0]

    assert world.apply_upgrade(0, "heavy_rounds")
    assert player.stats.bullet_damage == config.PlayerStats().bullet_damage + 1

    world.upgrade_levels[0]["plated_hull"] = 3
    max_hp = player.stats.max_hp
    hp = player.hp

    assert not world.apply_upgrade(0, "plated_hull")
    assert player.stats.max_hp == max_hp
    assert player.hp == hp
    assert not world.apply_upgrade(99, "heavy_rounds")
