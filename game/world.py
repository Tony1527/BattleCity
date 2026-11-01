from __future__ import annotations

import math
import random

import pygame

import config
from game.effects import Effects
from game.enemies import Enemy, make_enemy
from game.entities import Base, Bullet, Player
from game.geometry import in_bounds, point_to_tile, tile_center, tile_rect
from game.input import PlayerInput
from game.levelgen import Level, generate_level
from game.pathfinding import astar
from game.skills import Grenade, compute_laser, point_near_segment
from game.upgrades import apply_upgrade as _apply_upgrade

_BULLET_SUBSTEP = 6.0
_MOVE_SUBSTEP = 1.0
_EPSILON = 1e-9


class World:
    def __init__(
        self,
        level_index: int,
        seed: int | None = None,
        player_stats: list[config.PlayerStats] | None = None,
        upgrade_levels: list[dict[str, int]] | None = None,
    ) -> None:
        self.level_index = int(level_index)
        self.seed = self.level_index if seed is None else int(seed)
        self.random = random.Random(self.seed)
        self.level: Level = generate_level(self.seed)
        self.grid: list[list[config.Tile]] = self.level.grid

        self.status = "playing"
        self.elapsed = 0.0
        self.quota_remaining = 0
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

        self.base = Base(config.BASE_TILES)
        self.shared_lives = config.SHARED_LIVES + sum(
            stats.extra_lives for stats in self.player_stats
        )
        self.base.reset_for_level(
            sum(stats.base_shield for stats in self.player_stats)
        )

        self.enemies: list[Enemy] = []
        self.bullets: list[Bullet] = []
        self.grenades: list = []
        self.lasers: list = []
        self.boss = None
        self.effects = Effects()

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
            return self.grid[ty][tx] != config.Tile.STEEL

        return astar(start, goal, passable)

    def move_entity(
        self,
        entity,
        direction: config.Direction,
        dt: float,
    ) -> bool:
        direction = config.Direction(direction)
        entity.direction = direction
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
        self._update_skills(dt)
        self._update_spawning(dt)
        if self.status != "playing":
            return

        for player in self.players:
            player.update_timers(dt)
        self._respawn_players()
        self._update_players(dt, player_inputs)
        self._update_bullets(dt)
        if self.status != "playing":
            return
        self._update_enemies(dt)
        self.enemies = [enemy for enemy in self.enemies if enemy.alive]
        self._check_defeat()

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

    def spawn_enemy(
        self,
        kind: str,
        tile: tuple[int, int] | None = None,
    ) -> Enemy:
        if tile is None:
            tile = self.random.choice(config.ENEMY_SPAWNS)
        enemy = make_enemy(kind, tile)
        self.enemies.append(enemy)
        return enemy

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

        self.effects.burst(center, config.ENEMY_ORANGE, count=24)
        self.effects.shake(6.0)

    def throw_grenade(self, player: Player) -> bool:
        if (
            player is None
            or not player.alive
            or player.eliminated
            or player.grenade_timer > 0.0
        ):
            return False

        stats = player.stats
        grenade = Grenade(
            player.center,
            player.direction,
            owner_id=player.player_id,
            damage=stats.grenade_damage,
            radius=stats.grenade_radius,
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
            or player.laser_timer > 0.0
        ):
            return False

        stats = player.stats
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

        self.effects.shake(2.0)
        return True

    def resolve_grenade(self, grenade: Grenade) -> None:
        if grenade.exploded:
            return
        grenade.exploded = True

        points = grenade.explosion_points()
        hit_enemies: set[int] = set()
        hit_players: set[int] = set()
        player_damage = round(
            grenade.damage * config.GRENADE_FRIENDLY_FACTOR
        )

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

            for player in self.players:
                if not player.alive or player.eliminated:
                    continue
                if id(player) in hit_players:
                    continue
                if point.distance_to(player.center) > grenade.radius:
                    continue
                hit_players.add(id(player))
                self.damage_player(player, player_damage)

            self.effects.burst(point, config.ENEMY_ORANGE, count=18)

        self.effects.shake(5.0)

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

    def _update_spawning(self, dt: float) -> None:
        return None

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
            if player_input.move is not None:
                self.move_entity(player, player_input.move, dt)
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
                enemy.update(dt, self)

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
