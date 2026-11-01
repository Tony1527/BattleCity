import pygame
import pytest

import config
from game.effects import Effects
from game.entities import Bullet
from game.enemies import make_enemy
from game.geometry import tile_center, tile_rect
from game.input import PlayerInput
from game.world import World


def empty_grid():
    return [
        [config.Tile.EMPTY for _ in range(config.GRID_COLS)]
        for _ in range(config.GRID_ROWS)
    ]


def open_world(seed=1):
    world = World(0, seed=seed)
    world.grid = empty_grid()
    world.level.grid = world.grid
    return world


def test_burst_creates_particles_that_age_and_disappear():
    effects = Effects()

    assert effects.particles == []
    assert effects.shake_amount == 0.0

    effects.burst((50, 50), (255, 80, 40), count=7)

    assert len(effects.particles) == 7
    assert all(particle.life > 0 for particle in effects.particles)
    assert all(particle.color == (255, 80, 40) for particle in effects.particles)

    starting_lives = [particle.life for particle in effects.particles]
    effects.update(0.01)
    assert all(
        particle.life < starting
        for particle, starting in zip(effects.particles, starting_lives)
    )

    effects.update(10.0)
    assert effects.particles == []


def test_shake_decays_to_zero_and_offset_is_zero_when_calm():
    effects = Effects()

    assert effects.offset() == (0, 0)

    effects.shake(5.0)
    assert effects.shake_amount == pytest.approx(5.0)
    offset_x, offset_y = effects.offset()
    assert abs(offset_x) <= 5
    assert abs(offset_y) <= 5

    effects.update(1.0)
    assert effects.shake_amount == 0.0
    assert effects.offset() == (0, 0)


def test_draw_renders_particles_on_a_headless_surface():
    surface = pygame.Surface((320, 240))
    surface.fill((0, 0, 0))
    effects = Effects()
    effects.burst((160, 120), (255, 0, 0), count=4)

    effects.draw(surface)

    assert surface.get_at((160, 120))[:3] != (0, 0, 0)


def test_world_constructs_level_players_base_and_shared_lives():
    stats = [
        config.PlayerStats(max_hp=4, extra_lives=1, base_shield=2),
        config.PlayerStats(extra_lives=2, base_shield=1),
    ]

    world = World(2, seed=7, player_stats=stats)

    assert world.level_index == 2
    assert world.seed == 7
    assert world.status == "playing"
    assert world.grid == world.level.grid
    assert [player.pos for player in world.players] == [
        tile_center(*spawn) for spawn in config.PLAYER_SPAWNS
    ]
    assert [player.player_id for player in world.players] == [0, 1]
    assert world.base.hp == config.BASE_HP
    assert world.base.shield == 3
    assert world.shared_lives == config.SHARED_LIVES + 1 + 2
    assert world.quota_remaining == config.ENEMY_QUOTA[2]
    assert world.elapsed == 0.0
    assert world.enemies == []
    assert world.bullets == []
    assert world.grenades == []
    assert world.lasers == []
    assert world.boss is None
    assert world.base_entrances == config.BASE_ENTRANCES
    assert len(world.upgrade_levels) == len(world.players)


def test_world_defaults_match_spec_literals():
    world = World(0, seed=1)

    assert config.SHARED_LIVES == 3
    assert world.shared_lives == 3
    assert config.BASE_HP == 3
    assert world.base.max_hp == 3
    assert world.base.hp == 3


def test_base_entrances_is_a_data_attribute():
    world = World(0, seed=1)

    assert not callable(world.base_entrances)
    assert world.base_entrances == config.BASE_ENTRANCES
    assert tuple(world.base_entrances) == config.BASE_ENTRANCES


def test_grid_shares_the_level_object_and_stays_fresh():
    world = World(0, seed=1)

    assert world.grid is world.level.grid

    world.grid[5][5] = config.Tile.BRICK
    world.destroy_brick(5, 5)

    assert world.grid[5][5] == config.Tile.EMPTY
    assert world.level.grid[5][5] == config.Tile.EMPTY


def test_move_entity_is_blocked_by_brick_and_steel_but_slides_on_free_axis():
    for blocker in (config.Tile.BRICK, config.Tile.STEEL):
        world = open_world()
        player = world.players[0]
        player.pos = tile_center(4, 5)
        world.grid[5][5] = blocker

        moved = world.move_entity(player, config.Direction.RIGHT, 1.0)

        assert moved
        assert player.rect.right <= tile_rect(5, 5).left
        blocked_x = player.pos.x

        moved_up = world.move_entity(player, config.Direction.UP, 1.0)

        assert moved_up
        assert player.pos.x == blocked_x
        assert player.pos.y < tile_center(4, 5).y


def test_move_entity_stays_inside_the_playfield():
    world = open_world()
    player = world.players[0]
    player.pos = tile_center(1, 5)
    start_x = player.pos.x

    moved = world.move_entity(player, config.Direction.LEFT, 10.0)

    assert moved
    assert player.pos.x < start_x
    assert player.pos.x == pytest.approx(
        config.PLAYFIELD_RECT.left + config.PLAYER_SIZE / 2
    )
    assert player.rect.left == config.PLAYFIELD_RECT.left


def test_friendly_bullet_destroys_brick_and_disappears():
    world = open_world()
    world.grid[5][5] = config.Tile.BRICK
    bullet = Bullet(
        tile_center(4, 5),
        config.Direction.RIGHT,
        speed=config.PLAYER_BULLET_SPEED,
        friendly=True,
    )
    world.bullets.append(bullet)

    world.update(0.2, [])

    assert not bullet.alive
    assert world.bullets == []
    assert not world.is_brick(5, 5)


def test_bullet_hits_steel_and_dies_without_destroying_it():
    world = open_world()
    world.grid[5][5] = config.Tile.STEEL
    bullet = Bullet(
        tile_center(4, 5),
        config.Direction.RIGHT,
        speed=config.PLAYER_BULLET_SPEED,
        friendly=True,
    )
    world.bullets.append(bullet)

    world.update(0.2, [])

    assert not bullet.alive
    assert world.bullets == []
    assert world.is_steel(5, 5)
    assert world.grid[5][5] == config.Tile.STEEL


def test_bullet_substeps_do_not_tunnel_through_walls():
    world = open_world()
    world.grid[5][5] = config.Tile.BRICK
    bullet = Bullet(
        tile_center(1, 5),
        config.Direction.RIGHT,
        speed=5000.0,
        friendly=True,
    )
    world.bullets.append(bullet)

    world.update(0.1, [])

    assert not bullet.alive
    assert not world.is_brick(5, 5)


def test_friendly_bullets_do_not_damage_players_or_base():
    world = open_world()
    player = world.players[0]

    player_bullet = Bullet(
        player.center, config.Direction.RIGHT, speed=0.0, friendly=True
    )
    world.bullets.append(player_bullet)
    world.update(0.0, [])

    assert player.hp == player.max_hp
    assert player_bullet.alive

    base_bullet = Bullet(
        world.base.center, config.Direction.RIGHT, speed=0.0, friendly=True
    )
    world.bullets.append(base_bullet)
    world.update(0.0, [])

    assert world.base.hp == config.BASE_HP
    assert base_bullet.alive


def test_enemy_bullets_damage_players_and_base():
    world = open_world()
    player = world.players[0]
    player_bullet = Bullet(
        player.center, config.Direction.RIGHT, speed=0.0, friendly=False
    )
    world.bullets.append(player_bullet)

    world.update(0.0, [])

    assert player.hp == player.max_hp - 1
    assert player.invuln == pytest.approx(config.HIT_INVULN)
    assert not player_bullet.alive

    other = open_world()
    base_bullet = Bullet(
        other.base.center, config.Direction.RIGHT, speed=0.0, friendly=False
    )
    other.bullets.append(base_bullet)

    other.update(0.0, [])

    assert other.base.hp == config.BASE_HP - 1
    assert not base_bullet.alive


def test_hit_invulnerability_blocks_a_second_enemy_bullet():
    world = open_world()
    player = world.players[0]

    first = Bullet(
        player.center, config.Direction.RIGHT, speed=0.0, friendly=False
    )
    world.bullets.append(first)
    world.update(0.0, [])

    damaged_hp = player.hp
    assert damaged_hp == player.max_hp - 1
    assert player.invuln > 0.0

    second = Bullet(
        player.center, config.Direction.RIGHT, speed=0.0, friendly=False
    )
    world.bullets.append(second)
    world.update(0.0, [])

    assert player.hp == damaged_hp
    assert not second.alive
    assert world.bullets == []


def test_respawn_invulnerability_blocks_enemy_bullets():
    world = open_world()
    player = world.players[0]
    player.hp = 1
    player.invuln = 0.0
    world.damage_player(player, 1)
    world.update(config.RESPAWN_DELAY, [])

    assert player.alive
    assert player.invuln == pytest.approx(config.RESPAWN_INVULN)

    hp = player.hp
    bullet = Bullet(
        player.center, config.Direction.RIGHT, speed=0.0, friendly=False
    )
    world.bullets.append(bullet)
    world.update(0.0, [])

    assert player.hp == hp
    assert not bullet.alive


def test_base_shield_absorbs_damage_before_hp():
    world = open_world()
    world.base.reset_for_level(shield=2)

    world.damage_base(1)
    assert world.base.shield == 1
    assert world.base.hp == config.BASE_HP

    world.damage_base(1)
    assert world.base.shield == 0
    assert world.base.hp == config.BASE_HP

    world.damage_base(1)
    assert world.base.shield == 0
    assert world.base.hp == config.BASE_HP - 1


def test_out_of_bounds_bullets_are_removed():
    world = open_world()
    bullet = Bullet(
        (config.PLAYFIELD_RECT.right + 10, tile_center(5, 5).y),
        config.Direction.RIGHT,
        speed=0.0,
        friendly=True,
    )
    world.bullets.append(bullet)

    world.update(0.0, [])

    assert not bullet.alive
    assert world.bullets == []


def test_enemy_fire_spawns_enemy_bullets_that_damage_players_and_base():
    world = open_world()
    player = world.players[0]
    enemy = make_enemy("tracker", world.point_to_tile(player.center))
    enemy.pos = pygame.Vector2(player.center)
    world.enemies.append(enemy)

    bullet = world.enemy_fire(enemy, config.Direction.RIGHT)

    assert bullet is not None
    assert not bullet.friendly
    assert bullet.owner_id == -1
    assert bullet.speed == enemy.spec.bullet_speed
    assert bullet.damage == enemy.spec.bullet_damage
    assert bullet in world.bullets

    world.update(0.0, [])
    assert player.hp == player.max_hp - enemy.spec.bullet_damage

    base_world = open_world()
    base_enemy = make_enemy(
        "tracker", base_world.point_to_tile(base_world.base.center)
    )
    base_enemy.pos = pygame.Vector2(base_world.base.center)
    base_world.enemies.append(base_enemy)
    base_bullet = base_world.enemy_fire(base_enemy, config.Direction.RIGHT)

    assert base_bullet is not None
    base_world.update(0.0, [])
    assert base_world.base.hp == config.BASE_HP - base_enemy.spec.bullet_damage


def test_demolisher_blast_damages_players_bricks_and_the_base():
    world = open_world()
    enemy = make_enemy("demolisher", (11, 10))
    player = world.players[0]
    player.pos = tile_center(10, 10)
    player.invuln = 0.0
    world.grid[10][12] = config.Tile.BRICK

    world.demolisher_blast(enemy)

    assert player.hp == player.max_hp - config.DEMOLISHER_BLAST_DAMAGE
    assert not world.is_brick(12, 10)
    assert world.base.hp == config.BASE_HP - config.DEMOLISHER_BLAST_DAMAGE
    assert world.base.alive


def test_friendly_bullets_damage_enemies():
    world = open_world()
    enemy = make_enemy("tracker", (5, 5))
    world.enemies.append(enemy)
    bullet = Bullet(enemy.center, config.Direction.RIGHT, friendly=True)
    world.bullets.append(bullet)

    world.update(0.0, [])

    assert enemy.hp == enemy.max_hp - 1
    assert not bullet.alive
    assert world.bullets == []


def test_bullets_resolve_before_enemies_move():
    world = open_world()
    enemy = make_enemy("tracker", (5, 5))
    world.enemies.append(enemy)
    bullet = Bullet(enemy.center, config.Direction.RIGHT, friendly=True)
    world.bullets.append(bullet)

    world.update(0.5, [])

    assert enemy.hp == enemy.max_hp - 1


def test_destroyed_player_consumes_shared_life_and_respawns_invulnerable():
    world = open_world()
    player = world.players[0]
    player.hp = 1
    player.invuln = 0.0

    world.damage_player(player, 1)

    assert not player.alive
    assert not player.eliminated
    assert world.shared_lives == config.SHARED_LIVES - 1
    assert player.respawn_timer == pytest.approx(config.RESPAWN_DELAY)

    world.update(config.RESPAWN_DELAY, [])

    assert player.alive
    assert player.respawn_timer == 0.0
    assert player.invuln == pytest.approx(config.RESPAWN_INVULN)
    assert player.pos == tile_center(*config.PLAYER_SPAWNS[0])


def test_damage_player_ignores_an_already_dead_player():
    world = open_world()
    player = world.players[0]
    player.alive = False
    player.hp = 0
    player.respawn_timer = config.RESPAWN_DELAY
    lives = world.shared_lives

    world.damage_player(player, 1)

    assert world.shared_lives == lives
    assert player.respawn_timer == pytest.approx(config.RESPAWN_DELAY)
    assert not player.eliminated


def test_destroyed_player_with_no_shared_lives_is_eliminated():
    world = open_world()
    world.shared_lives = 0
    player = world.players[0]
    player.hp = 1
    player.invuln = 0.0

    world.damage_player(player, 1)

    assert not player.alive
    assert player.eliminated
    assert world.shared_lives == 0

    world.update(10.0, [])
    assert not player.alive


def test_both_players_eliminated_sets_status_lost():
    world = open_world()
    world.shared_lives = 0

    for player in world.players:
        player.hp = 1
        player.invuln = 0.0
        world.damage_player(player, 1)

    assert all(player.eliminated for player in world.players)
    assert world.status == "lost"


def test_base_destroyed_sets_status_lost():
    world = open_world()

    world.damage_base(config.BASE_HP)

    assert world.base.hp == 0
    assert not world.base.alive
    assert world.status == "lost"


def test_lost_status_freezes_further_updates():
    world = open_world()
    world.status = "lost"
    player = world.players[0]
    start_pos = pygame.Vector2(player.pos)
    start_elapsed = world.elapsed

    world.update(5.0, [PlayerInput(move=config.Direction.RIGHT)])

    assert world.elapsed == start_elapsed
    assert player.pos == start_pos
    assert world.bullets == []


def test_update_short_circuits_after_mid_frame_defeat():
    world = open_world()
    world.base.hp = 1
    world.base.shield = 0
    enemy = make_enemy("tracker", (5, 5))
    world.enemies.append(enemy)
    enemy_pos = pygame.Vector2(enemy.pos)
    bullet = Bullet(
        world.base.center, config.Direction.RIGHT, speed=0.0, friendly=False
    )
    world.bullets.append(bullet)

    world.update(0.5, [])

    assert world.status == "lost"
    assert not world.base.alive
    assert enemy.pos == enemy_pos


def test_player_fire_respects_fire_interval():
    world = open_world()
    inputs = [PlayerInput(shoot=True), PlayerInput()]

    world.update(0.0, inputs)

    assert len(world.bullets) == 1
    bullet = world.bullets[0]
    assert bullet.friendly
    assert bullet.owner_id == 0
    assert bullet.direction == config.Direction.UP
    assert bullet.speed == config.PLAYER_BULLET_SPEED
    assert bullet.damage == config.PLAYER_BULLET_DAMAGE

    world.update(0.0, inputs)
    assert len(world.bullets) == 1

    world.update(config.PLAYER_FIRE_INTERVAL, inputs)
    assert len(world.bullets) == 2


def test_find_path_treats_brick_as_passable_and_steel_as_blocked():
    world = open_world()
    world.grid[5][5] = config.Tile.BRICK

    path = world.find_path((4, 5), (6, 5))

    assert path == [(4, 5), (5, 5), (6, 5)]

    world.grid[5][5] = config.Tile.STEEL

    path = world.find_path((4, 5), (6, 5))

    assert path is not None
    assert (5, 5) not in path
    assert world.is_steel(5, 5)
    assert not world.is_brick(5, 5)


def test_destroy_brick_clears_only_bricks():
    world = open_world()
    world.grid[5][5] = config.Tile.BRICK

    world.destroy_brick(5, 5)

    assert world.grid[5][5] == config.Tile.EMPTY
    assert not world.is_brick(5, 5)

    world.grid[5][6] = config.Tile.STEEL
    world.destroy_brick(5, 6)
    assert world.grid[5][6] == config.Tile.STEEL


def test_tile_helpers_round_trip():
    world = open_world()

    assert world.point_to_tile(tile_center(3, 4)) == (3, 4)
    assert world.tile_center(3, 4) == tile_center(3, 4)
