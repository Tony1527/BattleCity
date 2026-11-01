import pygame
import pytest

import config
from game.boss import Boss
from game.entities import Bullet
from game.enemies import EliteEnemy, make_enemy
from game.geometry import tile_center
from game.levelgen import validate_level
from game.world import World


def empty_grid():
    return [
        [config.Tile.EMPTY for _ in range(config.GRID_COLS)]
        for _ in range(config.GRID_ROWS)
    ]


def wave_world(level=0, seed=1):
    world = World(level, seed=seed)
    world.grid = empty_grid()
    world.level.grid = world.grid
    world.players = []
    world.base.reset_for_level(shield=10_000)
    return world


def combat_world(level=0, seed=1):
    world = World(level, seed=seed)
    world.grid = empty_grid()
    world.level.grid = world.grid
    world.max_active = 0
    world.quota_remaining = 0
    world.spawn_quota = 0
    world.spawn_timer = float("inf")
    world.base.reset_for_level()
    return world


@pytest.mark.parametrize("level", range(config.BOSS_LEVEL))
def test_level_start_sets_quota_spawn_settings_and_elite(level):
    world = World(level, seed=level)

    assert world.quota_remaining == config.ENEMY_QUOTA[level]
    assert world.spawn_quota == config.ENEMY_QUOTA[level]
    assert world.max_active == config.MAX_ACTIVE_ENEMIES[level]
    assert world.spawn_timer == pytest.approx(config.SPAWN_START_DELAY)
    assert world.boss is None

    elites = [enemy for enemy in world.enemies if isinstance(enemy, EliteEnemy)]
    expected_elites = 1 if level in config.ELITE_LEVELS else 0
    assert len(elites) == expected_elites
    assert world.elite_spawned is bool(expected_elites)


def test_boss_level_creates_boss_at_top_center_with_no_normal_waves():
    world = World(config.BOSS_LEVEL, seed=11)

    assert isinstance(world.boss, Boss)
    assert world.boss.alive
    assert world.boss.pos.x == pytest.approx(config.PLAYFIELD_RECT.centerx)
    assert world.boss.rect.top >= config.PLAYFIELD_RECT.top
    assert world.quota_remaining == 0
    assert world.spawn_quota == 0
    assert world.max_active == 0
    assert world.elite_spawned is False
    assert world.enemies == []
    assert world.remaining_enemies == 1

    world.base.reset_for_level(shield=10_000)
    world.update(config.SPAWN_START_DELAY + 0.01, [])
    assert world.enemies == []


def test_spawn_timer_uses_start_delay_and_level_interval():
    world = wave_world(0)
    starting_quota = world.quota_remaining

    world._update_spawning(config.SPAWN_START_DELAY / 2)
    assert world.enemies == []

    world._update_spawning(config.SPAWN_START_DELAY / 2)
    assert len(world.enemies) == 1
    assert world.quota_remaining == starting_quota - 1
    assert world.spawn_timer == pytest.approx(config.SPAWN_INTERVAL[0])

    world._update_spawning(config.SPAWN_INTERVAL[0] - 0.1)
    assert len(world.enemies) == 1

    world._update_spawning(0.2)
    assert len(world.enemies) == 2
    assert world.quota_remaining == starting_quota - 2


def test_spawning_stops_at_max_active_and_refills_a_freed_slot():
    world = wave_world(0)

    for _ in range(10):
        world._update_spawning(10.0)

    assert len(world.enemies) == config.MAX_ACTIVE_ENEMIES[0]
    assert world.quota_remaining == (
        config.ENEMY_QUOTA[0] - config.MAX_ACTIVE_ENEMIES[0]
    )

    world._update_spawning(10.0)
    assert len(world.enemies) == config.MAX_ACTIVE_ENEMIES[0]

    world.enemies[0].alive = False
    quota_before = world.quota_remaining
    world._update_spawning(0.0)

    assert len(world.enemies) == config.MAX_ACTIVE_ENEMIES[0] + 1
    assert world.quota_remaining == quota_before - 1


def test_elite_level_spawns_one_elite_that_does_not_consume_quota():
    world = wave_world(3)
    starting_quota = config.ENEMY_QUOTA[3]

    elites = [enemy for enemy in world.enemies if isinstance(enemy, EliteEnemy)]
    assert len(elites) == 1
    assert world.elite_spawned is True
    assert world.quota_remaining == starting_quota

    for index in range(10):
        world._update_spawning(10.0)
        for enemy in world.enemies:
            if world.point_to_tile(enemy.center) in config.ENEMY_SPAWNS:
                enemy.pos = tile_center(6 + index % 4, 5 + index // 4)

    living = [enemy for enemy in world.enemies if enemy.alive]
    assert len(living) == config.MAX_ACTIVE_ENEMIES[3]
    assert sum(isinstance(enemy, EliteEnemy) for enemy in living) == 1
    assert world.quota_remaining == (
        starting_quota - (config.MAX_ACTIVE_ENEMIES[3] - 1)
    )

    elites[0].alive = False
    world._update_spawning(0.0)

    living = [enemy for enemy in world.enemies if enemy.alive]
    assert len(living) == config.MAX_ACTIVE_ENEMIES[3]
    assert sum(isinstance(enemy, EliteEnemy) for enemy in living) == 0
    assert world.elite_spawned is True


def test_spawns_avoid_steel_and_occupied_spawn_tiles():
    world = wave_world(0)
    world.max_active = 10
    world.quota_remaining = 5
    world.spawn_quota = 5
    world.spawn_timer = 0.0

    first, second, third = config.ENEMY_SPAWNS
    world.grid[first[1]][first[0]] = config.Tile.STEEL
    world.enemies = [make_enemy("tracker", second)]

    world._update_spawning(0.0)

    assert len(world.enemies) == 2
    spawn = world.enemies[-1]
    assert world.point_to_tile(spawn.center) == third
    assert all(
        not world.is_steel(*world.point_to_tile(enemy.center))
        for enemy in world.enemies
    )


def test_explicit_spawn_on_steel_reroutes_to_a_safe_tile():
    world = wave_world(0)
    tx, ty = config.ENEMY_SPAWNS[0]
    world.grid[ty][tx] = config.Tile.STEEL

    enemy = world.spawn_enemy("tracker", (tx, ty))

    assert world.point_to_tile(enemy.center) != (tx, ty)
    assert not world.is_steel(*world.point_to_tile(enemy.center))


def test_no_spawn_happens_when_every_spawn_tile_is_steel():
    world = wave_world(0)
    world.quota_remaining = 5
    world.spawn_quota = 5
    world.spawn_timer = 0.0

    for tx, ty in config.ENEMY_SPAWNS:
        world.grid[ty][tx] = config.Tile.STEEL

    world._update_spawning(10.0)

    assert world.enemies == []
    assert world.quota_remaining == 5


def test_remaining_enemies_counts_living_pending_and_the_boss():
    world = wave_world(0)
    world.quota_remaining = 2
    world.spawn_quota = 2
    alive_a = make_enemy("tracker", (5, 5))
    alive_b = make_enemy("gunner", (6, 5))
    dead = make_enemy("tracker", (7, 5))
    dead.alive = False
    world.enemies = [alive_a, alive_b, dead]

    assert world.remaining_enemies == 4

    boss_world = wave_world(config.BOSS_LEVEL)
    assert boss_world.remaining_enemies == 1
    boss_world.boss.take_damage(boss_world.boss.max_hp)
    assert boss_world.remaining_enemies == 0


def test_clear_requires_zero_quota_and_no_living_enemies():
    world = wave_world(0)
    world.quota_remaining = 0
    world.spawn_quota = 0
    enemy = make_enemy("tracker", (5, 5))
    world.enemies = [enemy]

    world.update(0.0, [])
    assert world.status == "playing"

    enemy.alive = False
    world.update(0.0, [])
    assert world.status == "cleared"

    world.update(0.0, [])
    assert world.status == "cleared"


def test_boss_bullet_kill_sets_victory_and_emits_particles():
    world = combat_world(config.BOSS_LEVEL)
    boss = world.boss
    assert boss is not None

    bullet = Bullet(
        boss.center,
        config.Direction.DOWN,
        speed=0.0,
        damage=boss.max_hp,
        friendly=True,
    )
    world.bullets.append(bullet)

    world.update(0.0, [])

    assert not boss.alive
    assert world.status == "victory"
    assert world.effects.particles != []


def test_enemy_fire_at_aims_a_bullet_that_damages_a_player():
    world = combat_world(0)
    player = world.players[0]
    player.pos = tile_center(8, 6)
    player.invuln = 0.0
    player.hp = player.max_hp

    origin = tile_center(8, 2)
    bullet = world.enemy_fire_at(origin, player.center, 300.0, 2)

    assert bullet in world.bullets
    assert not bullet.friendly
    assert bullet.owner_id == -1
    assert bullet.damage == 2
    assert bullet.velocity is not None

    world.update(1.0, [])

    assert player.hp == player.max_hp - 2


def test_radial_burst_uses_arbitrary_angles_not_only_cardinals():
    world = combat_world(0)
    origin = tile_center(8, 6)

    bullets = world.enemy_radial_burst(origin, 12, 260.0, 1)

    assert len(bullets) == 12
    assert all(not bullet.friendly for bullet in bullets)
    velocities = {
        (round(bullet.velocity.x, 3), round(bullet.velocity.y, 3))
        for bullet in bullets
    }
    assert len(velocities) == 12
    assert any(
        abs(bullet.velocity.x) > 0 and abs(bullet.velocity.y) > 0
        for bullet in bullets
    )

    world.update(0.01, [])
    displacements = [
        (bullet.pos.x - origin.x, bullet.pos.y - origin.y)
        for bullet in bullets
    ]
    assert any(abs(dx) > 0 and abs(dy) > 0 for dx, dy in displacements)


def test_boss_laser_damages_players_and_base():
    world = combat_world(0)
    player = world.players[0]
    player.pos = tile_center(8, 4)
    player.invuln = 0.0
    player.hp = player.max_hp

    origin = tile_center(8, 2)
    world.boss_laser(origin, config.Direction.DOWN)

    assert len(world.lasers) == 1
    assert player.hp == player.max_hp - config.BOSS_BULLET_DAMAGE

    base_hp = world.base.hp
    base_origin = pygame.Vector2(
        world.base.center.x,
        config.PLAYFIELD_RECT.top + config.TILE / 2,
    )
    world.boss_laser(base_origin, config.Direction.DOWN)

    assert len(world.lasers) == 2
    assert world.base.hp == base_hp - config.BOSS_BULLET_DAMAGE


def test_line_of_sight_is_blocked_by_brick_and_steel():
    world = combat_world(0)
    start = tile_center(2, 5)
    end = tile_center(6, 5)

    assert world.line_of_sight(start, end)

    world.grid[5][4] = config.Tile.BRICK
    assert not world.line_of_sight(start, end)

    world.grid[5][4] = config.Tile.STEEL
    assert not world.line_of_sight(start, end)

    world.grid[5][4] = config.Tile.EMPTY
    assert world.line_of_sight(start, end)


def test_find_path_routes_enemies_around_steel():
    world = combat_world(0)
    for ty in range(1, config.GRID_ROWS - 1):
        world.grid[ty][5] = config.Tile.STEEL

    path = world.find_path((4, 6), (6, 6))

    assert path is not None
    assert (5, 6) not in path
    assert all(not world.is_steel(*tile) for tile in path)


def test_demolisher_blast_damages_nearby_players_and_bricks():
    world = combat_world(0)
    player = world.players[0]
    player.pos = tile_center(5, 6)
    player.invuln = 0.0
    player.hp = player.max_hp
    world.grid[6][4] = config.Tile.BRICK
    world.grid[6][8] = config.Tile.BRICK

    enemy = make_enemy("demolisher", (5, 5))
    world.demolisher_blast(enemy)

    assert player.hp == player.max_hp - config.DEMOLISHER_BLAST_DAMAGE
    assert not world.is_brick(4, 6)
    assert world.is_brick(8, 6)
    assert world.base.hp == config.BASE_HP


@pytest.mark.parametrize("level", range(config.LEVEL_COUNT))
def test_full_eight_level_sequence_constructs_and_validates(level):
    world = World(level, seed=500 + level)

    assert world.level_index == level
    assert world.status == "playing"
    assert len(world.grid) == config.GRID_ROWS
    assert all(len(row) == config.GRID_COLS for row in world.grid)
    assert validate_level(world.level)

    if level == config.BOSS_LEVEL:
        assert isinstance(world.boss, Boss)
        assert world.boss.alive
    else:
        assert world.boss is None
        assert world.quota_remaining == config.ENEMY_QUOTA[level]
