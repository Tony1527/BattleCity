from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

from config import (
    BASE_ENTRANCES,
    BASE_TILES,
    BRICK_CHANCE,
    BRIDGE_COUNT,
    BRIDGE_MAX_CENTER,
    BRIDGE_MIN_CENTER,
    BRIDGE_MIN_SPACING,
    BRIDGE_WIDTH,
    CORRIDOR_BANDS,
    ENEMY_SPAWNS,
    GENERATION_RETRIES,
    GRID_COLS,
    GRID_ROWS,
    MAX_ROUTE_OVERLAP,
    MIN_BASE_ENTRANCE_DIRECTIONS,
    MIN_ROUTES,
    PLAYER_SPAWNS,
    RIVER_BANDS,
    RIVER_ROW_GAP,
    RIVER_ROW_MAX,
    RIVER_ROW_MIN,
    SPAWN_SAFE_RADIUS,
    STEEL_CHANCE,
    Direction,
    Tile,
)

from .geometry import in_bounds
from .pathfinding import astar, neighbors

_CORRIDOR_BRICK_CHANCE = 0.08
_MAX_CORRIDOR_BRICKS = 2
_DFS_ATTEMPTS = 40
_DFS_DEPTH_LIMIT = 200
_BRIDGE_CENTER_SLOTS = ((3, 4), (11, 12), (19, 20))


@dataclass
class Level:
    grid: list[list[Tile]]
    spawns: tuple[tuple[int, int], ...]
    base_tiles: tuple[tuple[int, int], ...]
    seed: int


def is_passable_for_routes(level: Level, tx: int, ty: int) -> bool:
    if not in_bounds(tx, ty):
        return False
    if ty >= len(level.grid) or tx >= len(level.grid[ty]):
        return False
    return level.grid[ty][tx] not in (Tile.STEEL, Tile.RIVER)


def _blank_grid() -> list[list[Tile]]:
    return [[Tile.EMPTY for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]


def _add_steel_border(grid: list[list[Tile]]) -> None:
    for tx in range(GRID_COLS):
        grid[0][tx] = Tile.STEEL
        grid[GRID_ROWS - 1][tx] = Tile.STEEL
    for ty in range(GRID_ROWS):
        grid[ty][0] = Tile.STEEL
        grid[ty][GRID_COLS - 1] = Tile.STEEL


def _protected_cells() -> set[tuple[int, int]]:
    cells = set(BASE_TILES) | set(BASE_ENTRANCES)
    for sx, sy in (*ENEMY_SPAWNS, *PLAYER_SPAWNS):
        for dy in range(-SPAWN_SAFE_RADIUS, SPAWN_SAFE_RADIUS + 1):
            for dx in range(-SPAWN_SAFE_RADIUS, SPAWN_SAFE_RADIUS + 1):
                if in_bounds(sx + dx, sy + dy):
                    cells.add((sx + dx, sy + dy))
    return cells


def _corridor_band(tx: int) -> int | None:
    for index, (start, end) in enumerate(CORRIDOR_BANDS):
        if start <= tx <= end:
            return index
    return None


def _choose_river_rows(
    rng: random.Random, count: int
) -> list[int]:
    rows: list[int] = []
    limit = max(0, int(count))
    for _ in range(limit):
        options = [
            row
            for row in range(RIVER_ROW_MIN, RIVER_ROW_MAX + 1)
            if all(abs(row - chosen) >= RIVER_ROW_GAP for chosen in rows)
        ]
        if not options:
            break
        rows.append(rng.choice(options))
    return rows


def _choose_bridge_centers(
    rng: random.Random, count: int
) -> list[int]:
    centers: list[int] = []
    for slot in _BRIDGE_CENTER_SLOTS[: max(0, int(count))]:
        candidate = rng.choice(slot)
        if all(
            abs(candidate - chosen) >= BRIDGE_MIN_SPACING
            for chosen in centers
        ):
            centers.append(candidate)

    while len(centers) < count:
        options = [
            center
            for center in range(BRIDGE_MIN_CENTER, BRIDGE_MAX_CENTER + 1)
            if all(
                abs(center - chosen) >= BRIDGE_MIN_SPACING
                for chosen in centers
            )
        ]
        if not options:
            break
        centers.append(rng.choice(options))
    return centers


def _carve_river(
    grid: list[list[Tile]],
    row: int,
    rng: random.Random,
) -> None:
    for tx in range(1, GRID_COLS - 1):
        grid[row][tx] = Tile.RIVER

    width = max(1, int(BRIDGE_WIDTH))
    for center in _choose_bridge_centers(rng, BRIDGE_COUNT):
        start = center - width // 2
        start = max(1, min(start, GRID_COLS - 1 - width))
        for tx in range(start, start + width):
            grid[row][tx] = Tile.BRIDGE


def _carve_rivers(
    grid: list[list[Tile]],
    rng: random.Random,
    count: int,
) -> None:
    for row in _choose_river_rows(rng, count):
        _carve_river(grid, row, rng)


def _river_count(level_index: int) -> int:
    if 0 <= level_index < len(RIVER_BANDS):
        return max(0, int(RIVER_BANDS[level_index]))
    return 0


def _build_grid(
    rng: random.Random, river_count: int = 0
) -> list[list[Tile]]:
    grid = _blank_grid()
    _add_steel_border(grid)
    protected = _protected_cells()
    corridor_bricks = [0] * len(CORRIDOR_BANDS)

    for ty in range(1, GRID_ROWS - 1):
        for tx in range(1, GRID_COLS - 1):
            if (tx, ty) in protected:
                continue
            band = _corridor_band(tx)
            if band is not None:
                if (
                    corridor_bricks[band] < _MAX_CORRIDOR_BRICKS
                    and rng.random() < _CORRIDOR_BRICK_CHANCE
                ):
                    grid[ty][tx] = Tile.BRICK
                    corridor_bricks[band] += 1
                continue
            roll = rng.random()
            if roll < STEEL_CHANCE:
                grid[ty][tx] = Tile.STEEL
            elif roll < STEEL_CHANCE + BRICK_CHANCE:
                grid[ty][tx] = Tile.BRICK

    for tx, ty in protected:
        grid[ty][tx] = Tile.EMPTY

    if river_count > 0:
        _carve_rivers(grid, rng, river_count)

    return grid


def _route_overlap(
    first: list[tuple[int, int]],
    second: list[tuple[int, int]],
) -> float:
    if not first or not second:
        return 0.0
    shared = len(set(first) & set(second))
    return shared / min(len(first), len(second))


def _entrance_direction(
    entrance: tuple[int, int],
    base_tiles: tuple[tuple[int, int], ...],
) -> Direction | None:
    if not base_tiles:
        return None
    center_x = sum(tx for tx, _ in base_tiles) / len(base_tiles)
    center_y = sum(ty for _, ty in base_tiles) / len(base_tiles)
    dx = entrance[0] - center_x
    dy = entrance[1] - center_y
    if abs(dx) >= abs(dy):
        return Direction.RIGHT if dx > 0 else Direction.LEFT
    return Direction.DOWN if dy > 0 else Direction.UP


def _random_dfs(
    start: tuple[int, int],
    goals: set[tuple[int, int]],
    passable: Callable[[int, int], bool],
    rng: random.Random,
) -> list[tuple[int, int]] | None:
    if not passable(*start):
        return None

    visited: set[tuple[int, int]] = set()
    path: list[tuple[int, int]] = []

    def search(tile: tuple[int, int], depth: int) -> list[tuple[int, int]] | None:
        visited.add(tile)
        path.append(tile)
        if tile in goals:
            return list(path)
        if depth >= _DFS_DEPTH_LIMIT:
            path.pop()
            return None

        options = [n for n in neighbors(*tile) if n not in visited and passable(*n)]
        rng.shuffle(options)
        for option in options:
            result = search(option, depth + 1)
            if result is not None:
                return result

        path.pop()
        return None

    return search(start, 0)


def _add_candidate(
    candidates: list[list[tuple[int, int]]],
    seen: set[tuple[tuple[int, int], ...]],
    path: list[tuple[int, int]] | None,
) -> None:
    if not path:
        return
    key = tuple(path)
    if key in seen:
        return
    seen.add(key)
    candidates.append(path)


def find_routes(level: Level, max_routes: int = 3) -> list[list[tuple[int, int]]]:
    if max_routes <= 0:
        return []

    def passable(tx: int, ty: int) -> bool:
        return is_passable_for_routes(level, tx, ty)

    goals = set(BASE_ENTRANCES)
    spawns = list(dict.fromkeys(level.spawns))
    candidates: list[list[tuple[int, int]]] = []
    seen: set[tuple[tuple[int, int], ...]] = set()

    for spawn_index, spawn in enumerate(spawns):
        for entrance in BASE_ENTRANCES:
            _add_candidate(candidates, seen, astar(spawn, entrance, passable))

        rng = random.Random(f"{level.seed}:{spawn_index}")
        for _ in range(_DFS_ATTEMPTS):
            _add_candidate(
                candidates,
                seen,
                _random_dfs(spawn, goals, passable, rng),
            )

    ordered = sorted(enumerate(candidates), key=lambda item: (len(item[1]), item[0]))

    selected: list[list[tuple[int, int]]] = []
    covered: set[tuple[int, int]] = set()

    for _, candidate in ordered:
        if len(selected) >= max_routes:
            break
        spawn = candidate[0]
        if spawn in covered:
            continue
        if any(
            _route_overlap(candidate, route) > MAX_ROUTE_OVERLAP
            for route in selected
        ):
            continue
        selected.append(candidate)
        covered.add(spawn)

    while len(selected) < max_routes:
        best: list[tuple[int, int]] | None = None
        best_key: tuple[float, int, int] | None = None
        for index, candidate in ordered:
            if candidate in selected:
                continue
            worst_overlap = max(
                (_route_overlap(candidate, route) for route in selected),
                default=0.0,
            )
            if worst_overlap > MAX_ROUTE_OVERLAP:
                continue
            key = (worst_overlap, len(candidate), index)
            if best_key is None or key < best_key:
                best_key = key
                best = candidate
        if best is None:
            break
        selected.append(best)

    return selected


def validate_level(level: Level) -> bool:
    routes = find_routes(level, max_routes=MIN_ROUTES)
    if len(routes) < MIN_ROUTES:
        return False

    spawns = set(level.spawns)
    if not spawns.issubset({route[0] for route in routes}):
        return False

    for first_index, first in enumerate(routes):
        for second in routes[first_index + 1 :]:
            if _route_overlap(first, second) > MAX_ROUTE_OVERLAP:
                return False

    entrances = set(BASE_ENTRANCES)
    directions = {
        _entrance_direction(route[-1], level.base_tiles)
        for route in routes
        if route[-1] in entrances
    }
    return len(directions) >= MIN_BASE_ENTRANCE_DIRECTIONS


def generate_level(seed: int, level_index: int = 0) -> Level:
    river_count = _river_count(level_index)
    seed_rng = random.Random(seed)
    for _ in range(GENERATION_RETRIES):
        attempt_seed = seed_rng.randrange(1 << 31)
        level = Level(
            grid=_build_grid(random.Random(attempt_seed), river_count),
            spawns=ENEMY_SPAWNS,
            base_tiles=BASE_TILES,
            seed=seed,
        )
        if validate_level(level):
            return level
    return fallback_level(river_count)


def fallback_level(river_count: int = 1) -> Level:
    grid = _blank_grid()
    _add_steel_border(grid)

    for tx, ty in (*BASE_TILES, *BASE_ENTRANCES):
        grid[ty][tx] = Tile.EMPTY

    bricks = (
        (7, 4),
        (8, 4),
        (9, 4),
        (7, 5),
        (8, 5),
        (9, 5),
        (14, 4),
        (15, 4),
        (16, 4),
        (14, 5),
        (15, 5),
        (16, 5),
        (7, 8),
        (8, 8),
        (9, 8),
        (14, 8),
        (15, 8),
        (16, 8),
    )
    for tx, ty in bricks:
        grid[ty][tx] = Tile.BRICK

    pillars = ((7, 6), (16, 6), (8, 7), (15, 7))
    for tx, ty in pillars:
        grid[ty][tx] = Tile.STEEL

    for tx, ty in _protected_cells():
        grid[ty][tx] = Tile.EMPTY

    if river_count > 0:
        _carve_rivers(grid, random.Random(0), river_count)

    return Level(
        grid=grid,
        spawns=ENEMY_SPAWNS,
        base_tiles=BASE_TILES,
        seed=0,
    )
