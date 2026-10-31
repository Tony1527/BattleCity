from __future__ import annotations

import heapq
from collections import deque
from collections.abc import Callable
from itertools import count

from .geometry import in_bounds

_NEIGHBOR_OFFSETS = ((0, -1), (-1, 0), (1, 0), (0, 1))


def neighbors(tx: int, ty: int) -> list[tuple[int, int]]:
    return [
        (tx + dx, ty + dy)
        for dx, dy in _NEIGHBOR_OFFSETS
        if in_bounds(tx + dx, ty + dy)
    ]


def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _reconstruct(
    came_from: dict[tuple[int, int], tuple[int, int]],
    current: tuple[int, int],
) -> list[tuple[int, int]]:
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path


def astar(
    start: tuple[int, int],
    goal: tuple[int, int],
    passable: Callable[[int, int], bool],
) -> list[tuple[int, int]] | None:
    if not in_bounds(*start) or not in_bounds(*goal):
        return None
    if not passable(*start) or not passable(*goal):
        return None
    if start == goal:
        return [start]

    counter = count()
    frontier: list[tuple[int, int, int, tuple[int, int]]] = [
        (_manhattan(start, goal), 0, next(counter), start)
    ]
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    cost: dict[tuple[int, int], int] = {start: 0}
    closed: set[tuple[int, int]] = set()

    while frontier:
        _, current_cost, _, current = heapq.heappop(frontier)
        if current in closed:
            continue
        if current == goal:
            return _reconstruct(came_from, current)
        closed.add(current)

        for neighbor in neighbors(*current):
            if neighbor in closed or not passable(*neighbor):
                continue
            new_cost = current_cost + 1
            previous_cost = cost.get(neighbor)
            if previous_cost is not None and new_cost >= previous_cost:
                continue
            cost[neighbor] = new_cost
            came_from[neighbor] = current
            priority = new_cost + _manhattan(neighbor, goal)
            heapq.heappush(
                frontier,
                (priority, new_cost, next(counter), neighbor),
            )

    return None


def bfs_distances(
    start: tuple[int, int],
    passable: Callable[[int, int], bool],
) -> dict[tuple[int, int], int]:
    if not in_bounds(*start) or not passable(*start):
        return {}

    distances = {start: 0}
    queue = deque([start])

    while queue:
        current = queue.popleft()
        next_distance = distances[current] + 1
        for neighbor in neighbors(*current):
            if neighbor in distances or not passable(*neighbor):
                continue
            distances[neighbor] = next_distance
            queue.append(neighbor)

    return distances
