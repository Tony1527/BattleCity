from __future__ import annotations

import pygame

import config
from game.geometry import in_bounds, tile_center


def _distance_squared(a: pygame.Vector2, b: pygame.Vector2) -> float:
    return a.distance_squared_to(b)


def _direction_between(
    start: pygame.Vector2, end: pygame.Vector2
) -> config.Direction | None:
    delta = end - start
    if delta.length_squared() == 0.0:
        return None
    return config.Direction.from_vector(delta.x, delta.y)


def _aligned_direction(
    start: pygame.Vector2, end: pygame.Vector2
) -> config.Direction | None:
    delta = end - start
    tolerance = config.TILE / 2
    if abs(delta.x) <= tolerance and abs(delta.y) > tolerance:
        return config.Direction.DOWN if delta.y > 0 else config.Direction.UP
    if abs(delta.y) <= tolerance and abs(delta.x) > tolerance:
        return config.Direction.RIGHT if delta.x > 0 else config.Direction.LEFT
    return None


def _line_is_clear(
    world, start: pygame.Vector2, end: pygame.Vector2
) -> bool:
    start = pygame.Vector2(start)
    end = pygame.Vector2(end)
    distance = start.distance_to(end)
    if distance == 0.0:
        return True

    start_tile = world.point_to_tile(start)
    end_tile = world.point_to_tile(end)
    steps = max(1, int(distance / (config.TILE / 2)))
    for step in range(1, steps):
        point = start.lerp(end, step / steps)
        tile = world.point_to_tile(point)
        if tile in (start_tile, end_tile):
            continue
        if world.is_brick(*tile):
            return False
    return True


def _next_path_tile(
    path: list[tuple[int, int]],
    current: tuple[int, int],
) -> tuple[int, int] | None:
    if not path:
        return None
    if current in path:
        index = path.index(current)
        return path[index + 1] if index + 1 < len(path) else None
    return path[0]


def _nearest_entrance(world, pos: pygame.Vector2):
    entrances = list(world.base_entrances)
    if not entrances:
        return None
    return min(
        entrances,
        key=lambda tile: _distance_squared(
            pos, world.tile_center(*tile)
        ),
    )


def _nearest_living_player(world, pos: pygame.Vector2):
    living = [player for player in world.players if player.alive]
    if not living:
        return None
    return min(
        living,
        key=lambda player: _distance_squared(
            pos, pygame.Vector2(player.center)
        ),
    )


class Enemy:
    def __init__(
        self,
        kind: str,
        pos: tuple[float, float] | pygame.Vector2,
        spec: config.EnemySpec | None = None,
        direction: config.Direction = config.Direction.UP,
    ):
        self.kind = kind
        self.spec = spec if spec is not None else config.ENEMY_SPECS[kind]
        self.pos = pygame.Vector2(pos)
        self.direction = config.Direction(direction)
        self.max_hp = self.spec.hp
        self.hp = self.max_hp
        self.speed = self.spec.speed
        self.fire_timer = 0.0
        self.telegraph = 0.0
        self.alive = True

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(
            round(self.pos.x - config.ENEMY_SIZE / 2),
            round(self.pos.y - config.ENEMY_SIZE / 2),
            config.ENEMY_SIZE,
            config.ENEMY_SIZE,
        )

    @property
    def center(self) -> pygame.Vector2:
        return pygame.Vector2(self.pos)

    def take_damage(self, amount: int, world) -> bool:
        if not self.alive or amount <= 0:
            return False

        self.hp = max(0, self.hp - amount)
        if self.hp == 0:
            self.alive = False
            return True
        return False

    def update(self, dt: float, world) -> None:
        if not self.alive:
            return

        self.fire_timer = max(0.0, self.fire_timer - dt)
        self._behave(dt, world)

    def _behave(self, dt: float, world) -> None:
        if self.kind == "demolisher":
            self._behave_demolisher(dt, world)
        elif self.kind in ("gunner", "elite"):
            self._behave_gunner(dt, world)
        else:
            self._behave_tracker(dt, world)

    def _emit_fire(self, world, direction: config.Direction) -> None:
        world.enemy_fire(self, direction)

    def _fire(
        self,
        world,
        direction: config.Direction,
        interval: float | None = None,
    ) -> bool:
        if self.fire_timer > 0.0:
            return False

        self.direction = config.Direction(direction)
        self._emit_fire(world, self.direction)
        self.fire_timer = (
            self.spec.fire_interval if interval is None else interval
        )
        return True

    def _advance(self, world, goal: tuple[int, int] | None, dt: float) -> None:
        if goal is None:
            return

        current = world.point_to_tile(self.pos)
        path = world.find_path(current, goal)
        if path:
            follow_path(self, world, path, dt)
            return

        direction = _direction_between(
            self.pos, world.tile_center(*goal)
        )
        if direction is not None:
            self.direction = direction
            world.move_enemy(self, direction, dt)

    def _behave_tracker(self, dt: float, world) -> None:
        entrance = _nearest_entrance(world, self.pos)
        if entrance is None:
            return

        target = world.tile_center(*entrance)
        direction = _aligned_direction(self.pos, target)
        if (
            direction is not None
            and self.pos.distance_to(target) <= self.spec.attack_range
            and _line_is_clear(world, self.pos, target)
        ):
            self._fire(world, direction)

        current = world.point_to_tile(self.pos)
        path = world.find_path(current, entrance)
        next_tile = _next_path_tile(path or [], current)
        if next_tile is not None and next_tile != current:
            if world.is_brick(*next_tile):
                brick_direction = _direction_between(
                    self.pos, world.tile_center(*next_tile)
                )
                if brick_direction is not None:
                    if self._fire(world, brick_direction):
                        return

        self._advance(world, entrance, dt)

    def _behave_gunner(self, dt: float, world) -> None:
        player = _nearest_living_player(world, self.pos)
        if player is None:
            entrance = _nearest_entrance(world, self.pos)
            if entrance is None:
                return
            target = world.tile_center(*entrance)
            direction = _aligned_direction(self.pos, target)
            if (
                direction is not None
                and self.pos.distance_to(target) <= self.spec.attack_range
                and _line_is_clear(world, self.pos, target)
            ):
                self._fire(world, direction)
            self._advance(world, entrance, dt)
            return

        target = pygame.Vector2(player.center)
        direction = _aligned_direction(self.pos, target)
        if (
            direction is not None
            and self.pos.distance_to(target) <= self.spec.attack_range
            and _line_is_clear(world, self.pos, target)
        ):
            self._fire(world, direction)
            return

        self._advance(world, self._reposition_goal(world, player), dt)

    def _reposition_goal(self, world, player) -> tuple[int, int]:
        player_tile = world.point_to_tile(player.center)
        for radius in range(4, 7):
            candidates = []
            for dx in range(-radius, radius + 1):
                dy = radius - abs(dx)
                for offset_y in (dy, -dy):
                    tile = (player_tile[0] + dx, player_tile[1] + offset_y)
                    if not in_bounds(*tile):
                        continue
                    if world.is_brick(*tile):
                        continue
                    candidates.append(tile)
            if candidates:
                return min(
                    candidates,
                    key=lambda tile: _distance_squared(
                        self.pos, world.tile_center(*tile)
                    ),
                )
        return player_tile

    def _behave_demolisher(self, dt: float, world) -> None:
        if self._blast_target(world) is not None:
            if self.telegraph <= 0.0:
                self.telegraph = config.DEMOLISHER_TELEGRAPH
            self.telegraph -= dt
            if self.telegraph <= 0.0:
                self.telegraph = 0.0
                world.demolisher_blast(self)
            return

        self.telegraph = 0.0
        entrance = _nearest_entrance(world, self.pos)
        if entrance is None:
            return

        current = world.point_to_tile(self.pos)
        path = world.find_path(current, entrance)
        next_tile = _next_path_tile(path or [], current)
        if next_tile is not None and next_tile != current:
            if world.is_brick(*next_tile):
                brick_direction = _direction_between(
                    self.pos, world.tile_center(*next_tile)
                )
                if brick_direction is not None:
                    if self._fire(
                        world,
                        brick_direction,
                        self.spec.fire_interval / 2,
                    ):
                        return

        self._advance(world, entrance, dt)

    def _blast_target(self, world):
        limit = config.DEMOLISHER_BLAST_RADIUS
        best = None
        best_distance = limit
        for player in world.players:
            if not player.alive:
                continue
            distance = self.pos.distance_to(player.center)
            if distance <= best_distance:
                best = player
                best_distance = distance
        for entrance in world.base_entrances:
            target = world.tile_center(*entrance)
            distance = self.pos.distance_to(target)
            if distance <= best_distance:
                best = target
                best_distance = distance
        return best


class EliteEnemy(Enemy):
    def __init__(
        self,
        pos: tuple[float, float] | pygame.Vector2,
        direction: config.Direction = config.Direction.UP,
    ):
        super().__init__(
            "elite",
            pos,
            spec=config.ENEMY_SPECS["gunner"],
            direction=direction,
        )
        self.shield = config.ELITE_SHIELD
        self.shield_timer = config.ELITE_SHIELD_REGEN
        self.summon_timer = config.ELITE_SUMMON_INTERVAL
        self.summons: list[Enemy] = []

    def take_damage(self, amount: int, world) -> bool:
        if not self.alive or amount <= 0:
            return False

        absorbed = min(self.shield, amount)
        self.shield -= absorbed
        amount -= absorbed
        self.shield_timer = config.ELITE_SHIELD_REGEN
        if amount == 0:
            return False

        self.hp = max(0, self.hp - amount)
        if self.hp == 0:
            self.alive = False
            return True
        return False

    def _emit_fire(self, world, direction: config.Direction) -> None:
        left = config.Direction((direction.value - 1) % len(config.Direction))
        right = config.Direction((direction.value + 1) % len(config.Direction))
        for shot in (left, direction, right):
            world.enemy_fire(self, shot)

    def _behave(self, dt: float, world) -> None:
        super()._behave(dt, world)
        self._update_shield(dt)
        self._update_summons(dt, world)

    def _update_shield(self, dt: float) -> None:
        self.shield_timer -= dt
        while self.shield_timer <= 0.0:
            if self.shield < config.ELITE_SHIELD:
                self.shield += 1
            self.shield_timer += config.ELITE_SHIELD_REGEN

    def _update_summons(self, dt: float, world) -> None:
        self.summon_timer -= dt
        if self.summon_timer > 0.0:
            return

        self.summon_timer = config.ELITE_SUMMON_INTERVAL
        self.summons = [summon for summon in self.summons if summon.alive]
        available = config.ELITE_MAX_SUMMONS - len(self.summons)
        if available <= 0:
            return

        tiles = self._summon_tiles(world)
        for index in range(available):
            spawn = world.spawn_enemy(
                "tracker", tiles[index % len(tiles)]
            )
            if spawn is not None:
                self.summons.append(spawn)

    def _summon_tiles(self, world) -> list[tuple[int, int]]:
        tx, ty = world.point_to_tile(self.pos)
        candidates = [
            (tx, ty - 1),
            (tx + 1, ty),
            (tx, ty + 1),
            (tx - 1, ty),
            (tx, ty),
        ]
        allowed = [
            tile
            for tile in candidates
            if in_bounds(*tile) and not world.is_brick(*tile)
        ]
        return allowed or [(tx, ty)]


def make_enemy(kind: str, tile: tuple[int, int]) -> Enemy:
    pos = tile_center(*tile)
    if kind == "elite":
        return EliteEnemy(pos)
    if kind not in config.ENEMY_SPECS:
        raise ValueError(f"unknown enemy kind: {kind}")
    return Enemy(kind, pos)


def follow_path(
    enemy: Enemy,
    world,
    path: list[tuple[int, int]],
    dt: float,
) -> config.Direction | None:
    current = world.point_to_tile(enemy.pos)
    next_tile = _next_path_tile(path, current)
    if next_tile is None or next_tile == current:
        return None

    current_center = world.tile_center(*current)
    direction = _direction_between(
        pygame.Vector2(current), pygame.Vector2(next_tile)
    )
    if direction is None:
        return None

    if direction in (config.Direction.LEFT, config.Direction.RIGHT):
        enemy.pos.y = current_center.y
    else:
        enemy.pos.x = current_center.x

    enemy.direction = direction
    world.move_enemy(enemy, direction, dt)
    return direction
