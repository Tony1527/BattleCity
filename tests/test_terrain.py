import pytest

import config
from game.entities import Bullet
from game.levelgen import validate_level
from game.skills import compute_laser
from game.world import World


@pytest.mark.parametrize("level_index", range(config.LEVEL_COUNT))
def test_all_levels_validate_with_rivers(level_index):
    world = World(level_index, seed=2000 + level_index)
    assert validate_level(world.level)
    if config.RIVER_BANDS[level_index] > 0:
        assert any(
            tile == config.Tile.RIVER
            for row in world.grid
            for tile in row
        )
        assert any(
            tile == config.Tile.BRIDGE
            for row in world.grid
            for tile in row
        )
    else:
        assert not any(
            tile == config.Tile.RIVER
            for row in world.grid
            for tile in row
        )


def test_river_blocks_tank_but_not_bullet_or_laser():
    world = World(1, seed=6)
    river = next(
        (tx, ty)
        for ty, row in enumerate(world.grid)
        for tx, tile in enumerate(row)
        if tile == config.Tile.RIVER
    )
    player = world.players[0]
    player.pos = world.tile_center(*river)
    assert world._rect_collides_tiles(player.rect) is True
    bullet = Bullet(player.center, config.Direction.RIGHT)
    bullet.pos = world.tile_center(*river)
    assert world._bullet_hits_wall(bullet) is False


def test_laser_passes_over_bridge_and_river():
    world = World(1, seed=6)
    grid = [
        [config.Tile.EMPTY for _ in range(config.GRID_COLS)]
        for _ in range(config.GRID_ROWS)
    ]
    grid[5][2] = config.Tile.RIVER
    grid[5][3] = config.Tile.BRIDGE
    origin = world.tile_center(2, 5)
    beam = compute_laser(
        origin, config.Direction.RIGHT, 3 * config.TILE, grid
    )
    assert beam.end.x == pytest.approx(origin.x + 3 * config.TILE)
