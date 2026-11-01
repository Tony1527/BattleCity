from __future__ import annotations

from typing import Iterable

import pygame

import config
from game.geometry import tile_rect


class Base:
    def __init__(self, tiles: Iterable[tuple[int, int]] = config.BASE_TILES):
        self.tiles = tuple(tiles)
        self.max_hp = config.BASE_HP
        self.hp = self.max_hp
        self.shield = 0
        self.alive = True

    @property
    def rect(self) -> pygame.Rect:
        rects = [tile_rect(tx, ty) for tx, ty in self.tiles]
        left = min(rect.left for rect in rects)
        top = min(rect.top for rect in rects)
        right = max(rect.right for rect in rects)
        bottom = max(rect.bottom for rect in rects)
        return pygame.Rect(left, top, right - left, bottom - top)

    @property
    def center(self) -> pygame.Vector2:
        return pygame.Vector2(self.rect.center)

    def take_damage(self, amount: int) -> None:
        if not self.alive or amount <= 0:
            return

        absorbed = min(self.shield, amount)
        self.shield -= absorbed
        amount -= absorbed
        self.hp = max(0, self.hp - amount)
        if self.hp == 0:
            self.alive = False

    def reset_for_level(self, shield: int = 0) -> None:
        self.hp = self.max_hp
        self.shield = max(0, int(shield))
        self.alive = True


class Bullet:
    def __init__(
        self,
        pos: tuple[float, float] | pygame.Vector2,
        direction: config.Direction,
        speed: float = config.PLAYER_BULLET_SPEED,
        damage: int = config.PLAYER_BULLET_DAMAGE,
        owner_id: int = -1,
        friendly: bool = True,
        pierce: bool = False,
        velocity: pygame.Vector2 | tuple[float, float] | None = None,
    ):
        self.pos = pygame.Vector2(pos)
        self.prev_pos = pygame.Vector2(pos)
        self.direction = config.Direction(direction)
        self.speed = speed
        self.damage = damage
        self.owner_id = owner_id
        self.friendly = friendly
        self.pierce = pierce
        self.velocity = (
            pygame.Vector2(velocity) if velocity is not None else None
        )
        self.alive = True

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(
            round(self.pos.x - config.BULLET_SIZE / 2),
            round(self.pos.y - config.BULLET_SIZE / 2),
            config.BULLET_SIZE,
            config.BULLET_SIZE,
        )

    def update(self, dt: float) -> None:
        self.prev_pos = pygame.Vector2(self.pos)
        if self.velocity is not None:
            self.pos += self.velocity * dt
            return
        dx, dy = self.direction.vector
        self.pos += pygame.Vector2(dx, dy) * self.speed * dt


class Player:
    def __init__(
        self,
        player_id: int,
        pos: tuple[float, float] | pygame.Vector2,
        stats: config.PlayerStats | None = None,
        direction: config.Direction = config.Direction.UP,
    ):
        self.player_id = player_id
        self.pos = pygame.Vector2(pos)
        self.direction = config.Direction(direction)
        self.stats = stats if stats is not None else config.PlayerStats()
        self.hp = self.stats.max_hp
        self.alive = True
        self.eliminated = False
        self.invuln = 0.0
        self.respawn_timer = 0.0
        self.fire_timer = 0.0
        self.grenade_timer = 0.0
        self.laser_timer = 0.0

    @property
    def max_hp(self) -> int:
        return self.stats.max_hp

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(
            round(self.pos.x - config.PLAYER_SIZE / 2),
            round(self.pos.y - config.PLAYER_SIZE / 2),
            config.PLAYER_SIZE,
            config.PLAYER_SIZE,
        )

    @property
    def center(self) -> pygame.Vector2:
        return pygame.Vector2(self.pos)

    def update_timers(self, dt: float) -> None:
        self.invuln = max(0.0, self.invuln - dt)
        self.respawn_timer = max(0.0, self.respawn_timer - dt)
        self.fire_timer = max(0.0, self.fire_timer - dt)
        self.grenade_timer = max(0.0, self.grenade_timer - dt)
        self.laser_timer = max(0.0, self.laser_timer - dt)

    def can_shoot(self) -> bool:
        return self.alive and not self.eliminated and self.fire_timer <= 0

    def shoot_reset(self) -> None:
        self.fire_timer = self.stats.fire_interval

    def take_damage(self, amount: int) -> bool:
        if not self.alive or self.invuln > 0:
            return False

        effective = max(1, round(amount * (1 - self.stats.damage_reduction)))
        self.hp = max(0, self.hp - effective)
        self.invuln = config.HIT_INVULN

        if self.hp == 0:
            self.alive = False
            return True
        return False

    def revive(self, pos: tuple[float, float] | pygame.Vector2) -> None:
        self.pos = pygame.Vector2(pos)
        self.hp = self.stats.max_hp
        self.alive = True
        self.eliminated = False
        self.invuln = config.RESPAWN_INVULN
        self.respawn_timer = 0.0
