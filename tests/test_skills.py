import pygame

import config
from game.geometry import tile_center, tile_rect
from game.skills import Cooldown, Grenade, compute_laser, point_near_segment


def empty_grid():
    return [
        [config.Tile.EMPTY for _ in range(config.GRID_COLS)]
        for _ in range(config.GRID_ROWS)
    ]


def test_cooldown_starts_ready_and_blocks_while_active():
    cooldown = Cooldown(2.0)

    assert cooldown.duration == 2.0
    assert cooldown.remaining == 0.0
    assert cooldown.ready
    assert cooldown.trigger()
    assert cooldown.remaining == 2.0
    assert not cooldown.ready
    assert not cooldown.trigger()
    assert cooldown.remaining == 2.0


def test_cooldown_becomes_ready_and_clamps_at_zero():
    cooldown = Cooldown(2.0)
    cooldown.trigger()

    cooldown.update(1.0)
    assert cooldown.remaining == 1.0
    assert not cooldown.ready

    cooldown.update(5.0)
    assert cooldown.remaining == 0.0
    assert cooldown.ready
    assert cooldown.trigger()


def test_grenade_flies_from_start_to_clamped_target_and_explodes_once():
    start = tile_center(5, 5)
    grenade = Grenade(start, config.Direction.RIGHT, owner_id=1)

    assert grenade.start == start
    assert grenade.target == start + pygame.Vector2(
        config.Direction.RIGHT.vector
    ) * config.GRENADE_RANGE
    assert grenade.duration == config.GRENADE_FLIGHT
    assert grenade.elapsed == 0.0
    assert grenade.owner_id == 1
    assert grenade.damage == config.GRENADE_DAMAGE
    assert grenade.radius == config.GRENADE_RADIUS
    assert grenade.split == 0
    assert not grenade.exploded
    assert grenade.position() == start
    assert grenade.height() == 0.0

    assert not grenade.update(config.GRENADE_FLIGHT / 2)
    assert grenade.position() == start + (
        grenade.target - start
    ) * 0.5
    assert grenade.height() == config.GRENADE_ARC_HEIGHT

    assert grenade.update(config.GRENADE_FLIGHT / 2)
    assert grenade.exploded
    assert grenade.position() == grenade.target
    assert grenade.height() == 0.0
    assert not grenade.update(config.GRENADE_FLIGHT)
    assert grenade.position() == grenade.target
    assert grenade.explosion_points() == [grenade.target]


def test_grenade_target_is_clamped_inside_playfield_margin():
    start = pygame.Vector2(
        config.PLAYFIELD_X + config.PLAYFIELD_WIDTH - 2,
        config.PLAYFIELD_Y + config.PLAYFIELD_HEIGHT - 2,
    )
    right = Grenade(start, config.Direction.RIGHT)
    down = Grenade(start, config.Direction.DOWN)

    max_x = config.PLAYFIELD_X + config.PLAYFIELD_WIDTH - config.GRENADE_MARGIN
    max_y = config.PLAYFIELD_Y + config.PLAYFIELD_HEIGHT - config.GRENADE_MARGIN
    assert right.target == pygame.Vector2(max_x, max_y)
    assert down.target == pygame.Vector2(max_x, max_y)


def test_grenade_split_offsets_points_perpendicular_to_travel():
    start = tile_center(2, 2)
    grenade = Grenade(start, config.Direction.UP, split=2)

    points = grenade.explosion_points()
    assert len(points) == 1 + grenade.split
    assert points[0] == grenade.target
    assert points[1] == grenade.target + pygame.Vector2(
        config.GRENADE_SPLIT_OFFSET, 0
    )
    assert points[2] == grenade.target + pygame.Vector2(
        -config.GRENADE_SPLIT_OFFSET, 0
    )


def test_laser_reaches_full_range_in_open_grid():
    origin = tile_center(0, 0)
    beam = compute_laser(
        origin, config.Direction.RIGHT, config.LASER_RANGE, empty_grid()
    )

    assert beam.origin == origin
    assert beam.direction == config.Direction.RIGHT
    assert beam.end == origin + pygame.Vector2(
        config.Direction.RIGHT.vector
    ) * config.LASER_RANGE
    assert beam.length == config.LASER_RANGE
    assert beam.brick_tile is None
    assert beam.life == config.LASER_LIFE


def test_laser_respects_upgraded_range_beyond_old_sample_cap():
    origin = tile_center(0, 0)
    max_range = config.LASER_RANGE + 3 * config.TILE

    beam = compute_laser(
        origin, config.Direction.RIGHT, max_range, empty_grid()
    )

    assert beam.length == max_range
    assert beam.end == origin + pygame.Vector2(
        config.Direction.RIGHT.vector
    ) * max_range
    assert beam.brick_tile is None


def test_laser_stops_at_steel_without_recording_a_brick():
    grid = empty_grid()
    grid[0][5] = config.Tile.STEEL
    origin = tile_center(0, 0)
    face = tile_rect(5, 0).left

    beam = compute_laser(origin, config.Direction.RIGHT, config.LASER_RANGE, grid)

    assert beam.brick_tile is None
    assert face - config.LASER_SAMPLE_STEP <= beam.end.x <= face


def test_laser_stops_at_first_brick_and_records_its_tile():
    grid = empty_grid()
    grid[0][5] = config.Tile.BRICK
    grid[0][7] = config.Tile.BRICK
    origin = tile_center(0, 0)
    face = tile_rect(5, 0).left

    beam = compute_laser(origin, config.Direction.RIGHT, config.LASER_RANGE, grid)

    assert beam.brick_tile == (5, 0)
    assert face - config.LASER_SAMPLE_STEP <= beam.end.x <= face
    assert beam.length < 7 * config.TILE - origin.x + config.PLAYFIELD_X


def test_laser_end_snaps_to_blocking_tile_face():
    for tile in (config.Tile.STEEL, config.Tile.BRICK):
        grid = empty_grid()
        grid[0][5] = tile
        origin = tile_center(0, 0) + pygame.Vector2(0.5, 0)

        beam = compute_laser(
            origin, config.Direction.RIGHT, config.LASER_RANGE, grid
        )

        assert beam.end.x == tile_rect(5, 0).left
        if tile == config.Tile.BRICK:
            assert beam.brick_tile == (5, 0)
        else:
            assert beam.brick_tile is None


def test_point_near_segment_uses_distance_and_tolerance():
    a = pygame.Vector2(0, 0)
    b = pygame.Vector2(100, 0)

    assert point_near_segment(pygame.Vector2(50, 5), a, b, 18.0)
    assert not point_near_segment(pygame.Vector2(50, 40), a, b, 18.0)
    assert point_near_segment(pygame.Vector2(-4, 0), a, b, 5.0)
    assert not point_near_segment(pygame.Vector2(-40, 0), a, b, 18.0)
    assert point_near_segment(pygame.Vector2(3, 4), a, a, 5.0)
    assert not point_near_segment(pygame.Vector2(3, 4), a, a, 4.0)
