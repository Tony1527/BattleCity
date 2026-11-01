from __future__ import annotations

import pytest

from config import (
    BASE_ENTRANCES,
    BASE_TILES,
    CORRIDOR_BANDS,
    ENEMY_SPAWNS,
    GRID_COLS,
    GRID_ROWS,
    LEVEL_COUNT,
    PLAYER_SPAWNS,
    RIVER_BANDS,
    Tile,
)
from game.levelgen import (
    Level,
    fallback_level,
    find_routes,
    generate_level,
    is_passable_for_routes,
    validate_level,
)


def _empty_grid() -> list[list[Tile]]:
    return [[Tile.EMPTY for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]


def _add_steel_border(grid: list[list[Tile]]) -> None:
    for tx in range(GRID_COLS):
        grid[0][tx] = Tile.STEEL
        grid[GRID_ROWS - 1][tx] = Tile.STEEL
    for ty in range(GRID_ROWS):
        grid[ty][0] = Tile.STEEL
        grid[ty][GRID_COLS - 1] = Tile.STEEL


def _open_level(seed: int = 0) -> Level:
    grid = _empty_grid()
    _add_steel_border(grid)
    for tx, ty in BASE_TILES:
        grid[ty][tx] = Tile.EMPTY
    for tx, ty in BASE_ENTRANCES:
        grid[ty][tx] = Tile.EMPTY
    return Level(
        grid=grid,
        spawns=ENEMY_SPAWNS,
        base_tiles=BASE_TILES,
        seed=seed,
    )


def _overlap(first: list[tuple[int, int]], second: list[tuple[int, int]]) -> float:
    return len(set(first) & set(second)) / min(len(first), len(second))


def _entrance_direction(entrance: tuple[int, int]) -> str:
    center_x = sum(tx for tx, _ in BASE_TILES) / len(BASE_TILES)
    center_y = sum(ty for _, ty in BASE_TILES) / len(BASE_TILES)
    dx = entrance[0] - center_x
    dy = entrance[1] - center_y
    if abs(dx) >= abs(dy):
        return "right" if dx > 0 else "left"
    return "down" if dy > 0 else "up"


def _assert_structural_invariants(level: Level) -> None:
    assert len(level.grid) == GRID_ROWS
    assert all(len(row) == GRID_COLS for row in level.grid)
    assert level.spawns == ENEMY_SPAWNS
    assert level.base_tiles == BASE_TILES

    base = set(BASE_TILES)
    for ty in range(GRID_ROWS):
        for tx in range(GRID_COLS):
            on_border = tx in (0, GRID_COLS - 1) or ty in (0, GRID_ROWS - 1)
            if not on_border:
                continue
            if (tx, ty) in base:
                assert level.grid[ty][tx] != Tile.STEEL
            else:
                assert level.grid[ty][tx] == Tile.STEEL

    for tx, ty in (*BASE_TILES, *BASE_ENTRANCES):
        assert level.grid[ty][tx] != Tile.STEEL

    for sx, sy in (*ENEMY_SPAWNS, *PLAYER_SPAWNS):
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                tx, ty = sx + dx, sy + dy
                if 0 <= tx < GRID_COLS and 0 <= ty < GRID_ROWS:
                    assert level.grid[ty][tx] != Tile.STEEL

    guard_y = min(ty for _, ty in BASE_TILES) - 2
    guard_tiles = {
        (tx, guard_y) for tx, _ in BASE_TILES
    }
    for start, end in CORRIDOR_BANDS:
        for tx in range(start, end + 1):
            for ty in range(1, GRID_ROWS - 1):
                if (tx, ty) in guard_tiles:
                    continue
                assert level.grid[ty][tx] != Tile.STEEL


def test_generate_level_is_deterministic():
    first = generate_level(1234)
    second = generate_level(1234)

    assert first == second
    assert first.grid == second.grid
    assert first.seed == 1234
    assert second.seed == 1234


@pytest.mark.parametrize("seed", range(10))
def test_generated_levels_validate(seed: int):
    level = generate_level(seed)

    assert level.seed == seed
    assert validate_level(level)


@pytest.mark.parametrize("seed", range(10))
def test_generated_levels_have_expected_structure(seed: int):
    _assert_structural_invariants(generate_level(seed))


def test_fallback_level_validates():
    level = fallback_level()

    assert validate_level(level)


def test_fallback_level_has_expected_structure():
    _assert_structural_invariants(fallback_level())


def test_fallback_has_bricks_and_steel_outside_corridors():
    level = fallback_level()
    corridor_cells = {
        (tx, ty)
        for start, end in CORRIDOR_BANDS
        for tx in range(start, end + 1)
        for ty in range(1, GRID_ROWS - 1)
    }
    outside = [
        (tx, ty)
        for ty in range(1, GRID_ROWS - 1)
        for tx in range(1, GRID_COLS - 1)
        if (tx, ty) not in corridor_cells
    ]

    assert any(level.grid[ty][tx] == Tile.BRICK for tx, ty in outside)
    assert any(level.grid[ty][tx] == Tile.STEEL for tx, ty in outside)


def test_full_steel_row_between_spawns_and_base_fails_validation():
    level = _open_level()
    for tx in range(1, GRID_COLS - 1):
        level.grid[6][tx] = Tile.STEEL

    assert validate_level(level) is False


def test_single_narrow_gap_fails_route_validation():
    level = _open_level()
    for tx in range(1, GRID_COLS - 1):
        level.grid[6][tx] = Tile.STEEL
    level.grid[6][11] = Tile.EMPTY

    assert validate_level(level) is False


def test_single_base_entrance_direction_fails_validation():
    level = _open_level()
    for tx, ty in BASE_ENTRANCES:
        if (tx, ty) != (11, 10):
            level.grid[ty][tx] = Tile.STEEL

    assert validate_level(level) is False


def test_shared_narrow_corridor_exceeds_route_overlap_limit():
    level = _open_level()
    for ty in range(5, 10):
        for tx in range(1, GRID_COLS - 1):
            level.grid[ty][tx] = Tile.STEEL
        level.grid[ty][11] = Tile.EMPTY

    assert validate_level(level) is False


def test_is_passable_for_routes_treats_brick_and_empty_as_open():
    level = _open_level()
    level.grid[3][3] = Tile.BRICK
    level.grid[4][3] = Tile.STEEL

    assert is_passable_for_routes(level, 3, 3) is True
    assert is_passable_for_routes(level, 3, 4) is False
    assert is_passable_for_routes(level, 1, 1) is True
    assert is_passable_for_routes(level, -1, 1) is False
    assert is_passable_for_routes(level, GRID_COLS, 1) is False


def test_find_routes_respects_max_routes_and_covers_every_spawn():
    level = generate_level(0)

    routes = find_routes(level, max_routes=3)

    assert len(routes) == 3
    assert {route[0] for route in routes} == set(level.spawns)
    assert all(route[-1] in set(BASE_ENTRANCES) for route in routes)
    for index, first in enumerate(routes):
        for second in routes[index + 1 :]:
            assert _overlap(first, second) <= 0.30
    assert len({_entrance_direction(route[-1]) for route in routes}) >= 2
    assert len(find_routes(level, max_routes=2)) <= 2


@pytest.mark.parametrize("level_index", range(LEVEL_COUNT))
def test_rivers_never_overwrite_player_spawn_safe_rows(level_index):
    if RIVER_BANDS[level_index] <= 0:
        return
    for seed in range(5):
        level = generate_level(seed, level_index)
        for ty, row in enumerate(level.grid):
            if any(tile in (Tile.RIVER, Tile.BRIDGE) for tile in row):
                assert ty <= 8


@pytest.mark.parametrize("level_index", range(LEVEL_COUNT))
def test_base_guard_places_one_steel_block_two_tiles_in_front(level_index):
    front_y = min(ty for _, ty in BASE_TILES) - 2
    front_columns = sorted({tx for tx, _ in BASE_TILES})
    for seed in range(5):
        level = generate_level(seed, level_index)
        assert any(
            level.grid[front_y][tx] == Tile.STEEL
            for tx in front_columns
        )


def test_fallback_level_has_the_base_guard_block():
    level = fallback_level(level_index=3)
    front_y = min(ty for _, ty in BASE_TILES) - 2
    front_columns = sorted({tx for tx, _ in BASE_TILES})
    assert any(level.grid[front_y][tx] == Tile.STEEL for tx in front_columns)
