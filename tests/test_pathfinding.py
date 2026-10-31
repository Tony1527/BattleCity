from __future__ import annotations

from config import GRID_COLS, GRID_ROWS
from game.pathfinding import astar, bfs_distances, neighbors


def _passable_region(max_x: int, max_y: int, walls: frozenset[tuple[int, int]] = frozenset()):
    def passable(tx: int, ty: int) -> bool:
        return 0 <= tx <= max_x and 0 <= ty <= max_y and (tx, ty) not in walls

    return passable


def _is_adjacent(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1


def test_neighbors_use_up_left_right_down_order_and_respect_bounds():
    assert neighbors(5, 5) == [(5, 4), (4, 5), (6, 5), (5, 6)]
    assert neighbors(0, 0) == [(1, 0), (0, 1)]
    assert neighbors(GRID_COLS - 1, GRID_ROWS - 1) == [
        (GRID_COLS - 1, GRID_ROWS - 2),
        (GRID_COLS - 2, GRID_ROWS - 1),
    ]


def test_astar_routes_around_steel_in_a_five_by_five_grid():
    walls = frozenset({(2, 0), (2, 1), (2, 2), (2, 3)})
    passable = _passable_region(4, 4, walls)

    path = astar((0, 0), (4, 0), passable)

    assert path is not None
    assert path[0] == (0, 0)
    assert path[-1] == (4, 0)
    assert all(passable(tx, ty) for tx, ty in path)
    assert all(_is_adjacent(a, b) for a, b in zip(path, path[1:]))
    assert len(path) == 13
    assert not set(path) & walls


def test_astar_returns_none_when_fully_walled():
    walls = frozenset((2, ty) for ty in range(5))
    passable = _passable_region(4, 4, walls)

    assert astar((0, 0), (4, 0), passable) is None


def test_astar_returns_none_when_start_or_goal_is_blocked():
    walls = frozenset({(0, 0), (4, 4)})
    passable = _passable_region(4, 4, walls)

    assert astar((0, 0), (4, 0), passable) is None
    assert astar((0, 0), (4, 4), passable) is None


def test_astar_includes_start_and_goal_when_identical():
    passable = _passable_region(4, 4)

    assert astar((1, 1), (1, 1), passable) == [(1, 1)]


def test_astar_is_deterministic():
    passable = _passable_region(4, 4, frozenset({(2, 0), (2, 1), (2, 2), (2, 3)}))

    assert astar((0, 0), (4, 0), passable) == astar((0, 0), (4, 0), passable)


def test_bfs_distances_on_open_grid():
    passable = _passable_region(4, 4)

    distances = bfs_distances((0, 0), passable)

    assert len(distances) == 25
    assert distances[(0, 0)] == 0
    assert distances[(4, 0)] == 4
    assert distances[(0, 4)] == 4
    assert distances[(4, 4)] == 8


def test_bfs_distances_respect_walls_and_blocked_start():
    walls = frozenset((2, ty) for ty in range(5))
    passable = _passable_region(4, 4, walls)

    distances = bfs_distances((0, 0), passable)

    assert (0, 0) in distances
    assert (4, 0) not in distances
    assert bfs_distances((2, 0), passable) == {}
