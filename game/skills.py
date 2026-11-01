from __future__ import annotations

import math

import pygame

import config
from game.geometry import in_bounds, point_to_tile, tile_rect


class Cooldown:
    def __init__(self, duration: float):
        self.duration = float(duration)
        self.remaining = 0.0

    @property
    def ready(self) -> bool:
        return self.remaining <= 0.0

    def trigger(self) -> bool:
        if not self.ready:
            return False
        self.remaining = self.duration
        return True

    def update(self, dt: float) -> None:
        self.remaining = max(0.0, self.remaining - dt)


class Grenade:
    def __init__(
        self,
        start: tuple[float, float] | pygame.Vector2,
        direction: config.Direction,
        owner_id: int = -1,
        damage: int = config.GRENADE_DAMAGE,
        radius: float = config.GRENADE_RADIUS,
        split: int = 0,
        duration: float = config.GRENADE_FLIGHT,
    ):
        self.start = pygame.Vector2(start)
        self.direction = config.Direction(direction)
        self.owner_id = owner_id
        self.damage = damage
        self.radius = radius
        self.split = max(0, int(split))
        self.duration = float(duration)
        self.elapsed = 0.0
        self.exploded = False
        self.target = self._clamped_target()

    def _clamped_target(self) -> pygame.Vector2:
        dx, dy = self.direction.vector
        target = self.start + pygame.Vector2(dx, dy) * config.GRENADE_RANGE
        min_x = config.PLAYFIELD_X + config.GRENADE_MARGIN
        max_x = (
            config.PLAYFIELD_X
            + config.PLAYFIELD_WIDTH
            - config.GRENADE_MARGIN
        )
        min_y = config.PLAYFIELD_Y + config.GRENADE_MARGIN
        max_y = (
            config.PLAYFIELD_Y
            + config.PLAYFIELD_HEIGHT
            - config.GRENADE_MARGIN
        )
        target.x = min(max(target.x, min_x), max_x)
        target.y = min(max(target.y, min_y), max_y)
        return target

    def _progress(self) -> float:
        if self.duration <= 0.0:
            return 1.0
        return min(1.0, self.elapsed / self.duration)

    def update(self, dt: float) -> bool:
        if self.exploded:
            return False
        self.elapsed = min(self.duration, self.elapsed + dt)
        if self.elapsed >= self.duration:
            self.exploded = True
            return True
        return False

    def position(self) -> pygame.Vector2:
        return self.start.lerp(self.target, self._progress())

    def height(self) -> float:
        t = self._progress()
        return 4.0 * config.GRENADE_ARC_HEIGHT * t * (1.0 - t)

    def explosion_points(self) -> list[pygame.Vector2]:
        points = [pygame.Vector2(self.target)]
        dx, dy = self.direction.vector
        perpendicular = pygame.Vector2(-dy, dx)
        for level in range(1, self.split + 1):
            side = 1 if level % 2 == 1 else -1
            distance = config.GRENADE_SPLIT_OFFSET * ((level + 1) // 2)
            points.append(
                pygame.Vector2(self.target)
                + perpendicular * distance * side
            )
        return points


class LaserBeam:
    def __init__(
        self,
        origin: tuple[float, float] | pygame.Vector2,
        end: tuple[float, float] | pygame.Vector2,
        direction: config.Direction,
        brick_tile: tuple[int, int] | None = None,
        life: float = config.LASER_LIFE,
    ):
        self.origin = pygame.Vector2(origin)
        self.end = pygame.Vector2(end)
        self.length = self.origin.distance_to(self.end)
        self.direction = config.Direction(direction)
        self.brick_tile = brick_tile
        self.life = float(life)

    def update(self, dt: float) -> None:
        self.life = max(0.0, self.life - dt)


def _tile_face_distance(
    origin: pygame.Vector2,
    direction: config.Direction,
    tile_x: int,
    tile_y: int,
) -> float:
    rect = tile_rect(tile_x, tile_y)
    if direction == config.Direction.RIGHT:
        return rect.left - origin.x
    if direction == config.Direction.LEFT:
        return origin.x - rect.right
    if direction == config.Direction.DOWN:
        return rect.top - origin.y
    return origin.y - rect.bottom


def compute_laser(
    origin: tuple[float, float] | pygame.Vector2,
    direction: config.Direction,
    max_range: float,
    grid: list[list[config.Tile]],
) -> LaserBeam:
    origin = pygame.Vector2(origin)
    direction = config.Direction(direction)
    dx, dy = direction.vector
    unit = pygame.Vector2(dx, dy)
    step = config.LASER_SAMPLE_STEP
    sample_count = min(
        math.ceil(float(max_range) / step), config.LASER_MAX_SAMPLES
    )
    limit = min(float(max_range), sample_count * step)
    brick_tile: tuple[int, int] | None = None
    distance = 0.0

    for sample in range(1, sample_count + 1):
        distance = min(sample * step, limit)
        tile_x, tile_y = point_to_tile(origin + unit * distance)
        if not in_bounds(tile_x, tile_y):
            break
        tile = grid[tile_y][tile_x]
        if tile in (config.Tile.BRICK, config.Tile.STEEL):
            if tile == config.Tile.BRICK:
                brick_tile = (tile_x, tile_y)
            distance = max(
                0.0, _tile_face_distance(origin, direction, tile_x, tile_y)
            )
            break
    else:
        distance = limit

    end = origin + unit * distance
    return LaserBeam(origin, end, direction, brick_tile)


def point_near_segment(
    point: tuple[float, float] | pygame.Vector2,
    a: tuple[float, float] | pygame.Vector2,
    b: tuple[float, float] | pygame.Vector2,
    tolerance: float,
) -> bool:
    point = pygame.Vector2(point)
    a = pygame.Vector2(a)
    b = pygame.Vector2(b)
    segment = b - a
    length_squared = segment.length_squared()
    if length_squared == 0.0:
        return point.distance_to(a) <= tolerance
    projection = (point - a).dot(segment) / length_squared
    projection = min(1.0, max(0.0, projection))
    closest = a + segment * projection
    return point.distance_to(closest) <= tolerance
