from __future__ import annotations

import math
import random
from collections import deque

import pygame

import config
from game.boss import Boss
from game.difficulty import get_profile, scaled_enemy_spec
from game.effects import Effects
from game.enemies import Enemy, make_enemy
from game.entities import Base, Bullet, Player
from game.geometry import in_bounds, point_to_tile, tile_center, tile_rect
from game.hazards import Trap
from game.input import PlayerInput
from game.levelgen import Level, generate_level
from game.pathfinding import astar
from game.pickups import Pickup, roll_pickup_kind
from game.skills import (
    Grenade,
    compute_laser,
    offset_laser_origin,
    point_near_segment,
)
from game.upgrades import apply_upgrade as _apply_upgrade

_BULLET_SUBSTEP = 6.0
_MOVE_SUBSTEP = 1.0
_EPSILON = 1e-9


def _level_value(values, level_index: int, default=0):
    if 0 <= level_index < len(values):
        return values[level_index]
    return default


def _point_rect_distance(
    point: tuple[float, float] | pygame.Vector2,
    rect: pygame.Rect,
) -> float:
    point = pygame.Vector2(point)
    dx = max(rect.left - point.x, 0.0, point.x - rect.right)
    dy = max(rect.top - point.y, 0.0, point.y - rect.bottom)
    return math.hypot(dx, dy)


class World:
    def __init__(
        self,
        level_index: int,
        seed: int | None = None,
        player_stats: list[config.PlayerStats] | None = None,
        upgrade_levels: list[dict[str, int]] | None = None,
        difficulty: str = "normal",
        shared_lives: int | None = None,
        base_hp: int | None = None,
        base_shield: int | None = None,
    ) -> None:
        self.level_index = int(level_index)
        self.difficulty = get_profile(difficulty)
        self.seed = self.level_index if seed is None else int(seed)
        self.random = random.Random(self.seed)
        self.level: Level = generate_level(self.seed, self.level_index)
        self.grid: list[list[config.Tile]] = self.level.grid
        self.traps: list[Trap] = [
            Trap(tile) for tile in self.level.traps
        ]
        self.pickups: list[Pickup] = []
        self.pickup_events: list[str] = []
        self.pickup_timer = config.ITEM_INITIAL_DELAY
        self.pickup_rng = random.Random(
            f"{self.seed}:{self.level_index}:pickups"
        )

        self.status = "playing"
        self.elapsed = 0.0
        self.quota_remaining = 0
        self.spawn_quota = 0
        self.spawn_timer = config.SPAWN_START_DELAY
        self.max_active = 0
        self.elite_target_count = 0
        self.elite_spawned_count = 0
        self.elite_spawn_timer = config.ELITE_SPAWN_INTERVAL
        self.playfield_rect = pygame.Rect(config.PLAYFIELD_RECT)
        self.base_entrances = config.BASE_ENTRANCES

        provided_stats = list(player_stats) if player_stats is not None else []
        self.player_stats: list[config.PlayerStats] = []
        self.players: list[Player] = []
        for player_id, spawn in enumerate(config.PLAYER_SPAWNS):
            stats = (
                provided_stats[player_id]
                if player_id < len(provided_stats)
                else config.PlayerStats()
            )
            self.player_stats.append(stats)
            self.players.append(
                Player(
                    player_id,
                    tile_center(*spawn),
                    stats=stats,
                    direction=config.Direction.UP,
                )
            )

        provided_levels = (
            list(upgrade_levels) if upgrade_levels is not None else []
        )
        self.upgrade_levels: list[dict[str, int]] = []
        for player_id in range(len(self.players)):
            levels = (
                provided_levels[player_id]
                if player_id < len(provided_levels)
                else {}
            )
            self.upgrade_levels.append(dict(levels))

        self.base = Base(
            config.BASE_TILES, max_hp=self.difficulty.base_hp
        )
        self.shared_lives = (
            config.SHARED_LIVES
            + sum(stats.extra_lives for stats in self.player_stats)
            if shared_lives is None
            else max(0, int(shared_lives))
        )
        starting_shield = (
            sum(stats.base_shield for stats in self.player_stats)
            if base_shield is None
            else max(0, int(base_shield))
        )
        self.base.reset_for_level(starting_shield)
        if base_hp is not None:
            self.base.hp = max(0, min(int(base_hp), self.base.max_hp))
            self.base.alive = self.base.hp > 0

        self.enemies: list[Enemy] = []
        self.bullets: list[Bullet] = []
        self.grenades: list = []
        self.lasers: list = []
        self.boss: Boss | None = None
        self.effects = Effects()
        self._start_level()

    @property
    def remaining_enemies(self) -> int:
        living = sum(1 for enemy in self.enemies if enemy.alive)
        boss_alive = 1 if self.boss is not None and self.boss.alive else 0
        pending_elites = max(
            0, self.elite_target_count - self.elite_spawned_count
        )
        return living + self.quota_remaining + boss_alive + pending_elites

    def point_to_tile(
        self, pos: tuple[float, float] | pygame.Vector2
    ) -> tuple[int, int]:
        return point_to_tile(pos)

    def tile_center(self, tx: int, ty: int) -> pygame.Vector2:
        return tile_center(tx, ty)

    def is_brick(self, tx: int, ty: int) -> bool:
        if not in_bounds(tx, ty):
            return False
        return self.grid[ty][tx] == config.Tile.BRICK

    def is_steel(self, tx: int, ty: int) -> bool:
        if not in_bounds(tx, ty):
            return False
        return self.grid[ty][tx] == config.Tile.STEEL

    def ai_placement_tile(self, tile: tuple[int, int]) -> bool:
        tx, ty = tile
        if not in_bounds(tx, ty):
            return False
        if self.grid[ty][tx] != config.Tile.EMPTY:
            return False
        if any(trap.tile == (tx, ty) for trap in self.traps):
            return False
        if self._tile_occupied(tx, ty):
            return False
        return True

    def destroy_brick(self, tx: int, ty: int) -> bool:
        if not self.is_brick(tx, ty):
            return False
        self.grid[ty][tx] = config.Tile.EMPTY
        self.effects.burst(tile_center(tx, ty), config.BRICK, count=8)
        self.effects.shake(1.5)
        return True

    def find_path(
        self,
        start: tuple[int, int],
        goal: tuple[int, int],
    ) -> list[tuple[int, int]] | None:
        def passable(tx: int, ty: int) -> bool:
            if not in_bounds(tx, ty):
                return False
            return self.grid[ty][tx] not in (
                config.Tile.STEEL,
                config.Tile.RIVER,
            )

        return astar(start, goal, passable)

    def line_of_sight(
        self,
        a: tuple[float, float] | pygame.Vector2,
        b: tuple[float, float] | pygame.Vector2,
    ) -> bool:
        start = pygame.Vector2(a)
        end = pygame.Vector2(b)
        distance = start.distance_to(end)
        if distance <= _EPSILON:
            return True

        start_tile = self.point_to_tile(start)
        end_tile = self.point_to_tile(end)
        steps = max(1, math.ceil(distance / (config.TILE / 4)))
        for step in range(1, steps):
            point = start.lerp(end, step / steps)
            tile = self.point_to_tile(point)
            if not in_bounds(*tile):
                return False
            if tile in (start_tile, end_tile):
                continue
            if self.grid[tile[1]][tile[0]] in (
                config.Tile.BRICK,
                config.Tile.STEEL,
            ):
                return False
        return True

    def move_entity(
        self,
        entity,
        direction: config.Direction,
        dt: float,
    ) -> bool:
        direction = config.Direction(direction)
        entity.direction = direction
        if getattr(entity, "immobilized", 0.0) > 0.0:
            return False
        if dt <= 0.0:
            return False

        speed = self._entity_speed(entity)
        distance = speed * dt
        if distance <= 0.0:
            return False

        dx, dy = direction.vector
        moved = False
        if dx != 0:
            moved = self._sweep_axis(entity, dx * distance, 0.0) or moved
        if dy != 0:
            moved = self._sweep_axis(entity, 0.0, dy * distance) or moved
        return moved

    def move_enemy(
        self,
        enemy: Enemy,
        direction: config.Direction,
        dt: float,
    ) -> bool:
        return self.move_entity(enemy, direction, dt)

    def _update_traps(self, dt: float) -> None:
        for trap in self.traps:
            trap.update(dt)

    def _trigger_trap(
        self,
        entity,
        previous_tile: tuple[int, int],
    ) -> None:
        if entity is None or not getattr(entity, "alive", True):
            return
        if not hasattr(entity, "immobilized"):
            return

        current_tile = self.point_to_tile(entity.center)
        if current_tile == previous_tile:
            return
        for trap in self.traps:
            if trap.tile != current_tile:
                continue
            if not trap.try_trigger():
                return
            entity.immobilized = config.TRAP_DURATION
            return

    def _update_pickups(self, dt: float) -> None:
        step = max(0.0, dt)
        self.pickups = [
            pickup for pickup in self.pickups if pickup.update(step)
        ]

        for player in self.players:
            if not player.alive or player.eliminated:
                continue
            for pickup in list(self.pickups):
                if not player.rect.colliderect(pickup.rect):
                    continue
                if self._apply_pickup(player, pickup):
                    self.pickups.remove(pickup)
                    self.pickup_events.append(pickup.kind)
                    self.effects.burst(
                        pickup.pos, self._pickup_color(pickup.kind), count=10
                    )

        if self.status != "playing":
            return

        self.pickup_timer -= step
        if self.pickup_timer > 0.0:
            return
        if len(self.pickups) < config.ITEM_MAX_ON_MAP:
            self._spawn_pickup()
        self.pickup_timer = self.pickup_rng.uniform(
            *config.ITEM_SPAWN_INTERVAL
        )

    def _pickup_color(self, kind: str) -> tuple[int, int, int]:
        if kind == "stim":
            return (92, 222, 244)
        if kind == "invincible":
            return (255, 214, 92)
        return (96, 232, 144)

    def _apply_pickup(self, player: Player, pickup: Pickup) -> bool:
        if player is None or not player.alive or player.eliminated:
            return False
        if pickup.kind == "repair":
            if player.hp >= player.max_hp:
                return False
            player.hp = min(
                player.max_hp, player.hp + config.ITEM_REPAIR_AMOUNT
            )
            return True
        if pickup.kind == "stim":
            player.stim_timer = config.ITEM_STIM_DURATION
            return True
        if pickup.kind == "invincible":
            player.invincible_timer = config.ITEM_INVINCIBLE_DURATION
            return True
        return False

    def _spawn_pickup(self) -> Pickup | None:
        candidates = self._pickup_candidate_tiles()
        if not candidates:
            return None
        tx, ty = self.pickup_rng.choice(candidates)
        pickup = Pickup(roll_pickup_kind(self.pickup_rng), tile_center(tx, ty))
        self.pickups.append(pickup)
        return pickup

    def _pickup_candidate_tiles(self) -> list[tuple[int, int]]:
        protected = self._pickup_protected_cells()
        trapped = {trap.tile for trap in self.traps}
        taken = {self.point_to_tile(pickup.pos) for pickup in self.pickups}
        reachable = self._pickup_reachable_tiles()

        candidates: list[tuple[int, int]] = []
        for ty in range(1, config.GRID_ROWS - 1):
            for tx in range(1, config.GRID_COLS - 1):
                if self.grid[ty][tx] != config.Tile.EMPTY:
                    continue
                tile = (tx, ty)
                if tile not in reachable:
                    continue
                if tile in protected or tile in trapped or tile in taken:
                    continue
                if self._pickup_near_base(tile):
                    continue
                if self._tile_occupied(tx, ty):
                    continue
                candidates.append(tile)
        return candidates

    def _pickup_protected_cells(self) -> set[tuple[int, int]]:
        cells = set(config.BASE_TILES) | set(config.BASE_ENTRANCES)
        radius = config.SPAWN_SAFE_RADIUS
        for sx, sy in (*config.ENEMY_SPAWNS, *config.PLAYER_SPAWNS):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if in_bounds(sx + dx, sy + dy):
                        cells.add((sx + dx, sy + dy))
        return cells

    def _pickup_near_base(self, tile: tuple[int, int]) -> bool:
        tx, ty = tile
        margin = config.ITEM_BASE_MARGIN
        return any(
            abs(tx - bx) <= margin and abs(ty - by) <= margin
            for bx, by in config.BASE_TILES
        )

    def _pickup_reachable_tiles(self) -> set[tuple[int, int]]:
        walkable = (config.Tile.EMPTY, config.Tile.BRIDGE)
        reachable: set[tuple[int, int]] = set()
        queue: deque[tuple[int, int]] = deque()

        for spawn in config.PLAYER_SPAWNS:
            if spawn in reachable:
                continue
            if not in_bounds(*spawn):
                continue
            if self.grid[spawn[1]][spawn[0]] not in walkable:
                continue
            reachable.add(spawn)
            queue.append(spawn)

        while queue:
            tx, ty = queue.popleft()
            for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                neighbor = (tx + dx, ty + dy)
                if neighbor in reachable:
                    continue
                nx, ny = neighbor
                if not in_bounds(nx, ny):
                    continue
                if self.grid[ny][nx] not in walkable:
                    continue
                reachable.add(neighbor)
                queue.append(neighbor)
        return reachable

    def update(
        self,
        dt: float,
        inputs: list[PlayerInput] | None = None,
    ) -> None:
        if self.status != "playing":
            return
        if dt < 0.0:
            dt = 0.0
        self.elapsed += dt
        player_inputs = list(inputs) if inputs is not None else []

        self.effects.update(dt)
        self._update_traps(dt)
        self._update_skills(dt)
        self._update_spawning(dt)
        self._update_elite_spawning(dt)
        if self.status != "playing":
            return

        for player in self.players:
            player.update_timers(dt)
        self._respawn_players()
        self._update_players(dt, player_inputs)
        self._update_pickups(dt)
        self._update_bullets(dt)
        if self.status != "playing":
            return
        self._update_enemies(dt)
        self.enemies = [enemy for enemy in self.enemies if enemy.alive]
        self._check_defeat()
        self._check_progression()

    def damage_player(self, player: Player, amount: int) -> None:
        if player is None or not player.alive or amount <= 0:
            return

        destroyed = player.take_damage(amount)
        if not destroyed:
            self.effects.shake(1.5)
            return

        self.effects.burst(
            player.center, self._player_color(player), count=20
        )
        self.effects.shake(4.0)

        if self.shared_lives > 0:
            self.shared_lives -= 1
            player.respawn_timer = config.RESPAWN_DELAY
        else:
            player.eliminated = True
            player.respawn_timer = 0.0

        self._check_defeat()

    def damage_base(self, amount: int) -> None:
        if amount <= 0 or not self.base.alive:
            return

        self.base.take_damage(amount)
        self.effects.burst(self.base.center, config.BRICK, count=16)
        self.effects.shake(4.0)
        if not self.base.alive:
            self.status = "lost"

    def enemy_fire(
        self,
        enemy: Enemy,
        direction: config.Direction,
    ) -> Bullet | None:
        if not enemy.alive:
            return None

        spec = enemy.spec
        if spec.bullet_speed <= 0.0:
            return None

        bullet = Bullet(
            enemy.center,
            config.Direction(direction),
            speed=spec.bullet_speed,
            damage=spec.bullet_damage,
            owner_id=-1,
            friendly=False,
        )
        self.bullets.append(bullet)
        return bullet

    def enemy_fire_at(
        self,
        origin: tuple[float, float] | pygame.Vector2,
        target: tuple[float, float] | pygame.Vector2,
        speed: float,
        damage: int,
    ) -> Bullet:
        origin_v = pygame.Vector2(origin)
        target_v = pygame.Vector2(target)
        delta = target_v - origin_v
        if delta.length_squared() > 0.0:
            direction = config.Direction.from_vector(delta.x, delta.y)
            velocity = delta.normalize() * speed
        else:
            direction = config.Direction.DOWN
            velocity = pygame.Vector2(0.0, 0.0)

        bullet = Bullet(
            origin_v,
            direction,
            speed=speed,
            damage=damage,
            owner_id=-1,
            friendly=False,
            velocity=velocity,
        )
        self.bullets.append(bullet)
        return bullet

    def enemy_radial_burst(
        self,
        origin: tuple[float, float] | pygame.Vector2,
        count: int,
        speed: float,
        damage: int,
    ) -> list[Bullet]:
        origin_v = pygame.Vector2(origin)
        bullets: list[Bullet] = []
        if count <= 0:
            return bullets

        for index in range(count):
            angle = math.tau * index / count
            velocity = pygame.Vector2(
                math.cos(angle) * speed, math.sin(angle) * speed
            )
            if velocity.length_squared() > 0.0:
                direction = config.Direction.from_vector(
                    velocity.x, velocity.y
                )
            else:
                direction = config.Direction.UP
            bullet = Bullet(
                origin_v,
                direction,
                speed=speed,
                damage=damage,
                owner_id=-1,
                friendly=False,
                velocity=velocity,
            )
            self.bullets.append(bullet)
            bullets.append(bullet)
        return bullets

    def boss_laser(
        self,
        origin: tuple[float, float] | pygame.Vector2,
        direction: config.Direction,
    ) -> None:
        direction = config.Direction(direction)
        origin_v = pygame.Vector2(origin)
        max_range = math.hypot(
            config.PLAYFIELD_WIDTH, config.PLAYFIELD_HEIGHT
        )
        beam = compute_laser(origin_v, direction, max_range, self.grid)
        self.lasers.append(beam)

        if beam.brick_tile is not None:
            self.destroy_brick(*beam.brick_tile)

        for player in self.players:
            if not player.alive or player.eliminated:
                continue
            if not point_near_segment(
                player.center,
                beam.origin,
                beam.end,
                config.LASER_HIT_TOLERANCE,
            ):
                continue
            self.damage_player(player, config.BOSS_BULLET_DAMAGE)

        if self.base.alive and point_near_segment(
            self.base.center,
            beam.origin,
            beam.end,
            config.TILE,
        ):
            self.damage_base(config.BOSS_BULLET_DAMAGE)

        self.effects.burst(beam.end, config.HOLO_WHITE, count=8)
        self.effects.shake(3.0)

    def _damage_boss(self, amount: int) -> bool:
        if self.boss is None or not self.boss.alive or amount <= 0:
            return False

        destroyed = self.boss.take_damage(amount)
        if destroyed:
            self._on_boss_dead()
        else:
            self.effects.burst(
                self.boss.center, config.ENEMY_ORANGE, count=5
            )
            self.effects.shake(1.5)
        return destroyed

    def spawn_enemy(
        self,
        kind: str,
        tile: tuple[int, int] | None = None,
    ) -> Enemy | None:
        if tile is not None and not self._tile_spawnable(*tile):
            tile = None
        if tile is None:
            tile = self._choose_spawn_tile()
        if tile is None:
            tile = self._fallback_spawn_tile()
        if tile is None:
            return None
        if kind == "elite":
            spec = scaled_enemy_spec("gunner", self.difficulty)
            enemy = make_enemy(
                kind,
                tile,
                spec=spec,
                elite_level=self.level_index,
                elite_hp_mult=self.difficulty.elite_hp_mult,
                elite_shield_mult=self.difficulty.elite_shield_mult,
            )
        else:
            enemy = make_enemy(
                kind,
                tile,
                spec=scaled_enemy_spec(kind, self.difficulty),
            )
        self.enemies.append(enemy)
        return enemy

    def _tile_spawnable(self, tx: int, ty: int) -> bool:
        if (tx, ty) in config.BASE_TILES:
            return False
        if (tx, ty) in config.BASE_ENTRANCES:
            return False
        return self.ai_placement_tile((tx, ty))

    def _fallback_spawn_tile(self) -> tuple[int, int] | None:
        for ty in range(1, config.GRID_ROWS - 1):
            for tx in range(1, config.GRID_COLS - 1):
                if self._tile_spawnable(tx, ty):
                    return (tx, ty)
        return None

    def _tile_occupied(self, tx: int, ty: int) -> bool:
        tile = tile_rect(tx, ty)
        for enemy in self.enemies:
            if enemy.alive and enemy.rect.colliderect(tile):
                return True
        if (
            self.boss is not None
            and self.boss.alive
            and self.boss.rect.colliderect(tile)
        ):
            return True
        for player in self.players:
            if (
                player.alive
                and not player.eliminated
                and player.rect.colliderect(tile)
            ):
                return True
        return False

    def _choose_spawn_tile(self) -> tuple[int, int] | None:
        spawns = list(config.ENEMY_SPAWNS)
        if not spawns:
            return None

        start = self.random.randrange(len(spawns))
        for offset in range(len(spawns)):
            tile = spawns[(start + offset) % len(spawns)]
            if not self._tile_spawnable(*tile):
                continue
            return tile
        return None

    def demolisher_blast(self, enemy: Enemy) -> None:
        center = pygame.Vector2(enemy.pos)
        radius = config.DEMOLISHER_BLAST_RADIUS

        for player in self.players:
            if (
                player.alive
                and not player.eliminated
                and center.distance_to(player.center) <= radius
            ):
                self.damage_player(player, config.DEMOLISHER_BLAST_DAMAGE)

        for ty in range(config.GRID_ROWS):
            for tx in range(config.GRID_COLS):
                if not self.is_brick(tx, ty):
                    continue
                if center.distance_to(tile_center(tx, ty)) <= radius:
                    self.destroy_brick(tx, ty)

        if self.base.alive and _point_rect_distance(
            center, self.base.rect
        ) <= radius:
            self.damage_base(config.DEMOLISHER_BLAST_DAMAGE)

        self.effects.burst(center, config.ENEMY_ORANGE, count=24)
        self.effects.shake(6.0)

    def throw_grenade(self, player: Player) -> bool:
        if (
            player is None
            or not player.alive
            or player.eliminated
            or player.immobilized > 0.0
            or player.grenade_timer > 0.0
        ):
            return False

        stats = player.stats
        radius = stats.grenade_radius * (
            config.STIM_GRENADE_RADIUS_MULT
            if player.stim_timer > 0.0
            else 1.0
        )
        grenade = Grenade(
            player.center,
            player.direction,
            owner_id=player.player_id,
            damage=stats.grenade_damage,
            radius=radius,
            split=stats.grenade_split,
        )
        self.grenades.append(grenade)
        player.grenade_timer = stats.grenade_cooldown
        self.effects.burst(
            player.center, self._player_color(player), count=3
        )
        return True

    def fire_laser(self, player: Player) -> bool:
        if (
            player is None
            or not player.alive
            or player.eliminated
            or player.immobilized > 0.0
            or player.laser_timer > 0.0
        ):
            return False

        stats = player.stats
        if player.stim_timer > 0.0:
            return self._fire_twin_laser(player, stats)

        beam = compute_laser(
            player.center,
            player.direction,
            stats.laser_range,
            self.grid,
        )
        self.lasers.append(beam)
        player.laser_timer = stats.laser_cooldown
        self.effects.burst(
            player.center, config.HOLO_WHITE, count=4
        )

        if beam.brick_tile is not None:
            self.destroy_brick(*beam.brick_tile)

        for enemy in self.enemies:
            if not enemy.alive:
                continue
            if not point_near_segment(
                enemy.center,
                beam.origin,
                beam.end,
                config.LASER_HIT_TOLERANCE,
            ):
                continue
            destroyed = enemy.take_damage(stats.laser_damage, self)
            if destroyed:
                self.effects.burst(
                    enemy.center, config.ENEMY_RED, count=16
                )
                self.effects.shake(2.5)
            else:
                self.effects.burst(
                    enemy.center, config.ENEMY_ORANGE, count=5
                )

        if (
            self.boss is not None
            and self.boss.alive
            and self.boss.rect.clipline(
                (beam.origin.x, beam.origin.y, beam.end.x, beam.end.y)
            )
        ):
            self._damage_boss(stats.laser_damage)

        self.effects.shake(2.0)
        self._check_progression()
        return True

    def _fire_twin_laser(self, player: Player, stats) -> bool:
        snapshot = [row[:] for row in self.grid]
        beams = [
            compute_laser(
                offset_laser_origin(
                    player.center,
                    player.direction,
                    side * config.LASER_TWIN_OFFSET,
                ),
                player.direction,
                stats.laser_range,
                snapshot,
            )
            for side in (-1.0, 1.0)
        ]
        self.lasers.extend(beams)
        player.laser_timer = stats.laser_cooldown
        self.effects.burst(player.center, config.HOLO_WHITE, count=4)

        damage = max(
            1,
            round(stats.laser_damage * config.LASER_TWIN_DAMAGE_FACTOR),
        )
        destroyed_bricks: set[tuple[int, int]] = set()
        hit_enemy_ids: set[int] = set()
        hit_boss = False

        for beam in beams:
            if (
                beam.brick_tile is not None
                and beam.brick_tile not in destroyed_bricks
            ):
                destroyed_bricks.add(beam.brick_tile)
                self.destroy_brick(*beam.brick_tile)

            for enemy in self.enemies:
                if not enemy.alive or id(enemy) in hit_enemy_ids:
                    continue
                if not point_near_segment(
                    enemy.center,
                    beam.origin,
                    beam.end,
                    config.LASER_HIT_TOLERANCE,
                ):
                    continue
                hit_enemy_ids.add(id(enemy))
                destroyed = enemy.take_damage(damage, self)
                if destroyed:
                    self.effects.burst(
                        enemy.center, config.ENEMY_RED, count=16
                    )
                    self.effects.shake(2.5)
                else:
                    self.effects.burst(
                        enemy.center, config.ENEMY_ORANGE, count=5
                    )

            if (
                not hit_boss
                and self.boss is not None
                and self.boss.alive
                and self.boss.rect.clipline(
                    (beam.origin.x, beam.origin.y, beam.end.x, beam.end.y)
                )
            ):
                hit_boss = True
                self._damage_boss(damage)

        self.effects.shake(2.0)
        self._check_progression()
        return True

    def resolve_grenade(self, grenade: Grenade) -> None:
        if grenade.exploded:
            return
        grenade.exploded = True

        points = grenade.explosion_points()
        hit_enemies: set[int] = set()
        hit_players: set[int] = set()
        hit_boss = False

        for point in points:
            for ty in range(config.GRID_ROWS):
                for tx in range(config.GRID_COLS):
                    if not self.is_brick(tx, ty):
                        continue
                    if point.distance_to(tile_center(tx, ty)) <= grenade.radius:
                        self.destroy_brick(tx, ty)

            for enemy in self.enemies:
                if not enemy.alive or id(enemy) in hit_enemies:
                    continue
                if point.distance_to(enemy.center) > grenade.radius:
                    continue
                hit_enemies.add(id(enemy))
                destroyed = enemy.take_damage(grenade.damage, self)
                if destroyed:
                    self.effects.burst(
                        enemy.center, config.ENEMY_RED, count=16
                    )
                else:
                    self.effects.burst(
                        enemy.center, config.ENEMY_ORANGE, count=5
                    )

            if (
                not hit_boss
                and self.boss is not None
                and self.boss.alive
                and _point_rect_distance(point, self.boss.rect)
                <= grenade.radius
            ):
                hit_boss = True
                self._damage_boss(grenade.damage)

            for player in self.players:
                if not player.alive or player.eliminated:
                    continue
                if id(player) in hit_players:
                    continue
                if point.distance_to(player.center) > grenade.radius:
                    continue
                hit_players.add(id(player))
                friendly_damage = max(
                    1,
                    round(
                        player.max_hp * config.GRENADE_FRIENDLY_FACTOR
                    ),
                )
                self.damage_player(player, friendly_damage)

            self.effects.burst(point, config.ENEMY_ORANGE, count=18)

        self.effects.shake(5.0)
        self._check_progression()

    def apply_upgrade(self, player_id: int, upgrade_id: str) -> bool:
        if not 0 <= player_id < len(self.players):
            return False

        player = self.players[player_id]
        stats = player.stats
        previous_max_hp = stats.max_hp
        if not _apply_upgrade(
            stats, self.upgrade_levels[player_id], upgrade_id
        ):
            return False

        gained = stats.max_hp - previous_max_hp
        if gained > 0:
            player.hp = min(stats.max_hp, player.hp + gained)
        return True

    def _update_skills(self, dt: float) -> None:
        for grenade in list(self.grenades):
            if grenade.exploded:
                continue
            if grenade.elapsed + dt >= grenade.duration:
                grenade.elapsed = grenade.duration
                self.resolve_grenade(grenade)
            else:
                grenade.update(dt)
        self.grenades = [
            grenade for grenade in self.grenades if not grenade.exploded
        ]

        for laser in self.lasers:
            laser.update(dt)
        self.lasers = [
            laser for laser in self.lasers if laser.life > 0.0
        ]

    def _clear_boss_arena(self) -> None:
        for ty in range(1, 5):
            for tx in range(6, 18):
                if in_bounds(tx, ty):
                    self.grid[ty][tx] = config.Tile.EMPTY

    def _start_level(self) -> None:
        self.elite_target_count = _level_value(
            config.ELITE_COUNTS, self.level_index
        )
        self.elite_spawned_count = 0
        self.elite_spawn_timer = config.ELITE_SPAWN_INTERVAL

        if self.level_index == config.BOSS_LEVEL:
            self._clear_boss_arena()
            self.boss = Boss(
                hp_mult=self.difficulty.boss_hp_mult,
                interval_mult=self.difficulty.boss_interval_mult,
            )
            self.quota_remaining = 0
            self.spawn_quota = 0
            self.max_active = 0
            self.spawn_timer = config.SPAWN_START_DELAY
        else:
            quota = _level_value(config.ENEMY_QUOTA, self.level_index)
            self.quota_remaining = quota
            self.spawn_quota = quota
            self.max_active = _level_value(
                config.MAX_ACTIVE_ENEMIES, self.level_index
            )
            self.spawn_timer = config.SPAWN_START_DELAY

        if self.elite_target_count > 0:
            self._spawn_elite()
            self.elite_spawn_timer = config.ELITE_SPAWN_INTERVAL

    def _spawn_elite(self) -> Enemy | None:
        if self.elite_spawned_count >= self.elite_target_count:
            return None
        tile = self._choose_spawn_tile()
        if tile is None:
            tile = self._fallback_spawn_tile()
        if tile is None:
            return None
        enemy = self.spawn_enemy("elite", tile)
        if enemy is not None:
            self.elite_spawned_count += 1
        return enemy

    def _active_elite_count(self) -> int:
        return sum(
            1
            for enemy in self.enemies
            if enemy.alive and enemy.kind == "elite"
        )

    def _update_elite_spawning(self, dt: float) -> None:
        if self.status != "playing":
            return
        if self.elite_spawned_count >= self.elite_target_count:
            return

        if (
            self.quota_remaining == 0
            and self.elite_spawn_timer > config.ELITE_RETRY_INTERVAL
        ):
            self.elite_spawn_timer = 0.0
        else:
            self.elite_spawn_timer = max(
                0.0, self.elite_spawn_timer - dt
            )

        if self.elite_spawn_timer > 0.0:
            return
        if self._active_elite_count() >= config.ELITE_MAX_ACTIVE:
            self.elite_spawn_timer = config.ELITE_RETRY_INTERVAL
            return
        if self._spawn_elite() is None:
            self.elite_spawn_timer = config.ELITE_RETRY_INTERVAL
            return
        self.elite_spawn_timer = config.ELITE_SPAWN_INTERVAL

    def _active_enemy_count(self) -> int:
        return sum(1 for enemy in self.enemies if enemy.alive)

    def _spawn_interval(self) -> float:
        return (
            _level_value(config.SPAWN_INTERVAL, self.level_index, 0.0)
            * self.difficulty.spawn_interval_mult
        )

    def _choose_enemy_kind(self) -> str:
        if self.level_index <= 1:
            pool = ("tracker", "tracker", "tracker", "gunner")
        elif self.level_index <= 4:
            pool = ("tracker", "tracker", "gunner", "demolisher")
        else:
            pool = ("tracker", "gunner", "gunner", "demolisher")
        return self.random.choice(pool)

    def _update_spawning(self, dt: float) -> None:
        if self.status != "playing" or self.boss is not None:
            return
        if self.quota_remaining <= 0:
            return

        self.spawn_timer -= dt
        if self.spawn_timer > 0.0:
            return
        if self._active_enemy_count() >= self.max_active:
            return

        tile = self._choose_spawn_tile()
        if tile is None:
            tile = self._fallback_spawn_tile()
        if tile is None:
            return

        enemy = self.spawn_enemy(self._choose_enemy_kind(), tile)
        if enemy is None:
            return
        self.quota_remaining -= 1
        self.spawn_quota = self.quota_remaining
        self.spawn_timer = self._spawn_interval()

    def _on_boss_dead(self) -> None:
        if self.status != "playing":
            return
        self.status = "victory"
        for enemy in self.enemies:
            enemy.alive = False
        self.enemies = []
        self.elite_spawned_count = self.elite_target_count
        if self.boss is not None:
            self.effects.burst(self.boss.center, config.ENEMY_RED, count=48)
            self.effects.burst(
                self.boss.center, config.HOLO_WHITE, count=24
            )
            self.effects.shake(10.0)

    def _check_progression(self) -> None:
        if self.status != "playing":
            return

        if self.level_index == config.BOSS_LEVEL:
            if self.boss is not None and not self.boss.alive:
                self._on_boss_dead()
            return

        if (
            self.quota_remaining <= 0
            and self.elite_spawned_count >= self.elite_target_count
            and not any(enemy.alive for enemy in self.enemies)
        ):
            self.status = "cleared"

    def _entity_speed(self, entity) -> float:
        speed = getattr(entity, "speed", None)
        if speed is None:
            stats = getattr(entity, "stats", None)
            speed = getattr(stats, "speed", 0.0) if stats is not None else 0.0
        return float(speed)

    def _entity_rect_at(self, entity, pos: pygame.Vector2) -> pygame.Rect:
        size = entity.rect.size
        return pygame.Rect(
            round(pos.x - size[0] / 2),
            round(pos.y - size[1] / 2),
            size[0],
            size[1],
        )

    def _sweep_axis(self, entity, dx: float, dy: float) -> bool:
        remaining = math.hypot(dx, dy)
        if remaining <= _EPSILON:
            return False
        step_x = dx / remaining
        step_y = dy / remaining
        moved = False

        while remaining > _EPSILON:
            step = min(_MOVE_SUBSTEP, remaining)
            candidate = pygame.Vector2(entity.pos)
            candidate.x += step_x * step
            candidate.y += step_y * step
            rect = self._entity_rect_at(entity, candidate)
            if not self.playfield_rect.contains(rect):
                break
            if self._rect_collides_tiles(rect):
                break
            entity.pos = candidate
            moved = True
            remaining -= step

        return moved

    def _rect_collides_tiles(self, rect: pygame.Rect) -> bool:
        left = max(
            0, (rect.left - config.PLAYFIELD_X) // config.TILE
        )
        right = min(
            config.GRID_COLS - 1,
            (rect.right - 1 - config.PLAYFIELD_X) // config.TILE,
        )
        top = max(0, (rect.top - config.PLAYFIELD_Y) // config.TILE)
        bottom = min(
            config.GRID_ROWS - 1,
            (rect.bottom - 1 - config.PLAYFIELD_Y) // config.TILE,
        )

        for ty in range(top, bottom + 1):
            for tx in range(left, right + 1):
                if self.grid[ty][tx] not in (
                    config.Tile.BRICK,
                    config.Tile.STEEL,
                    config.Tile.RIVER,
                ):
                    continue
                if rect.colliderect(tile_rect(tx, ty)):
                    return True
        return False

    def _player_color(self, player: Player) -> tuple[int, int, int]:
        return config.P1_BLUE if player.player_id == 0 else config.P2_AMBER

    def _respawn_position(self, player: Player) -> pygame.Vector2:
        if 0 <= player.player_id < len(config.PLAYER_SPAWNS):
            return tile_center(*config.PLAYER_SPAWNS[player.player_id])
        return pygame.Vector2(
            self.base.center.x,
            self.base.center.y - config.TILE,
        )

    def _respawn_players(self) -> None:
        for player in self.players:
            if player.alive or player.eliminated:
                continue
            if player.respawn_timer > 0.0:
                continue
            player.revive(self._respawn_position(player))
            self.effects.burst(
                player.center, self._player_color(player), count=12
            )
            self.effects.shake(2.0)

    def _update_players(
        self,
        dt: float,
        inputs: list[PlayerInput],
    ) -> None:
        for player_id, player in enumerate(self.players):
            if player_id >= len(inputs):
                break
            if not player.alive or player.eliminated:
                continue
            player_input = inputs[player_id]
            if player_input is None:
                continue
            if player.immobilized > 0.0:
                continue
            previous_tile = self.point_to_tile(player.center)
            if player_input.move is not None:
                self.move_entity(player, player_input.move, dt)
            self._trigger_trap(player, previous_tile)
            if player.immobilized > 0.0:
                continue
            if player_input.shoot and player.can_shoot():
                self._player_fire(player)

    def _player_fire(self, player: Player) -> Bullet:
        player.shoot_reset()
        bullet = Bullet(
            player.center,
            player.direction,
            speed=player.stats.bullet_speed,
            damage=player.stats.bullet_damage,
            owner_id=player.player_id,
            friendly=True,
        )
        self.bullets.append(bullet)
        self.effects.burst(
            player.center, self._player_color(player), count=3
        )
        return bullet

    def _update_enemies(self, dt: float) -> None:
        for enemy in list(self.enemies):
            if enemy.alive:
                previous_tile = self.point_to_tile(enemy.center)
                enemy.update(dt, self)
                self._trigger_trap(enemy, previous_tile)
        if self.boss is not None and self.boss.alive:
            self.boss.update(dt, self)

    def _update_bullets(self, dt: float) -> None:
        survivors = []
        for bullet in self.bullets:
            if not bullet.alive:
                continue
            self._advance_bullet(bullet, dt)
            if bullet.alive:
                survivors.append(bullet)
        self.bullets = survivors

    def _advance_bullet(self, bullet: Bullet, dt: float) -> None:
        bullet.prev_pos = pygame.Vector2(bullet.pos)
        if bullet.velocity is not None:
            travel = max(0.0, bullet.velocity.length() * dt)
            if travel > 0.0:
                unit = bullet.velocity.normalize()
            else:
                unit = pygame.Vector2(0.0, 0.0)
        else:
            dx, dy = bullet.direction.vector
            unit = pygame.Vector2(dx, dy)
            travel = max(0.0, bullet.speed * dt)
        steps = max(1, math.ceil(travel / _BULLET_SUBSTEP))
        step = travel / steps

        for _ in range(steps):
            bullet.pos += unit * step
            if self._bullet_hits_wall(bullet):
                return
            if self._bullet_hits_player(bullet):
                return
            if self._bullet_hits_base(bullet):
                return
            if self._bullet_hits_enemy(bullet):
                return
            if self._bullet_hits_boss(bullet):
                return

    def _bullet_hits_wall(self, bullet: Bullet) -> bool:
        tx, ty = self.point_to_tile(bullet.pos)
        if not in_bounds(tx, ty):
            bullet.alive = False
            return True

        tile = self.grid[ty][tx]
        if tile == config.Tile.BRICK:
            self.destroy_brick(tx, ty)
            bullet.alive = False
            return True
        if tile == config.Tile.STEEL:
            self.effects.burst(
                bullet.pos, config.STEEL, count=5
            )
            self.effects.shake(1.0)
            bullet.alive = False
            return True
        return False

    def _bullet_hits_player(self, bullet: Bullet) -> bool:
        if bullet.friendly:
            return False

        for player in self.players:
            if not player.alive or player.eliminated:
                continue
            if not bullet.rect.colliderect(player.rect):
                continue
            self.damage_player(player, bullet.damage)
            if not bullet.pierce:
                bullet.alive = False
            return True
        return False

    def _bullet_hits_base(self, bullet: Bullet) -> bool:
        if bullet.friendly or not self.base.alive:
            return False
        if not bullet.rect.colliderect(self.base.rect):
            return False
        self.damage_base(bullet.damage)
        if not bullet.pierce:
            bullet.alive = False
        return True

    def _bullet_hits_enemy(self, bullet: Bullet) -> bool:
        if not bullet.friendly:
            return False

        for enemy in self.enemies:
            if not enemy.alive:
                continue
            if not bullet.rect.colliderect(enemy.rect):
                continue
            destroyed = enemy.take_damage(bullet.damage, self)
            if destroyed:
                self.effects.burst(enemy.center, config.ENEMY_RED, count=16)
                self.effects.shake(2.5)
            else:
                self.effects.burst(enemy.center, config.ENEMY_ORANGE, count=5)
            if not bullet.pierce:
                bullet.alive = False
            return True
        return False

    def _bullet_hits_boss(self, bullet: Bullet) -> bool:
        if (
            not bullet.friendly
            or self.boss is None
            or not self.boss.alive
        ):
            return False
        if not bullet.rect.colliderect(self.boss.rect):
            return False

        destroyed = self.boss.take_damage(bullet.damage)
        if destroyed:
            self._on_boss_dead()
        else:
            self.effects.burst(
                self.boss.center, config.ENEMY_ORANGE, count=5
            )
            self.effects.shake(1.5)
        if not bullet.pierce:
            bullet.alive = False
        return True

    def _check_defeat(self) -> None:
        if self.status != "playing":
            return
        if not self.base.alive:
            self.status = "lost"
            return
        if self.players and all(
            player.eliminated for player in self.players
        ):
            self.status = "lost"
