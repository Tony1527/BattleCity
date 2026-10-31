from __future__ import annotations

from dataclasses import dataclass

import pygame

import config
from game.geometry import in_bounds, point_to_tile


@dataclass
class _PendingAttack:
    kind: str
    timer: float
    target: pygame.Vector2 | None = None
    direction: config.Direction | None = None


class Boss:
    def __init__(self, pos: tuple[float, float] | pygame.Vector2 | None = None):
        rect = config.PLAYFIELD_RECT
        if pos is None:
            pos = (
                rect.centerx,
                rect.top + config.BOSS_SIZE / 2 + config.BOSS_DRIFT_MARGIN,
            )

        self.pos = pygame.Vector2(pos)
        self.max_hp = config.BOSS_HP
        self.hp = self.max_hp
        self.phase = 1
        self.alive = True
        self.telegraph = 0.0
        self.telegraph_kind: str | None = None
        self.telegraph_target: pygame.Vector2 | None = None
        self.telegraph_direction: config.Direction | None = None
        self.phase_flash = 0.0

        self.aim_timer = config.BOSS_AIM_INTERVAL[0]
        self.radial_timer = config.BOSS_RADIAL_INTERVAL[0]
        self.laser_timer: float | None = None
        self.drift_direction = 1
        self._pending: list[_PendingAttack] = []
        self._entered_phase = 1
        self._aimed_shots = 0
        self._laser_shots = 0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(
            round(self.pos.x - config.BOSS_SIZE / 2),
            round(self.pos.y - config.BOSS_SIZE / 2),
            config.BOSS_SIZE,
            config.BOSS_SIZE,
        )

    @property
    def center(self) -> pygame.Vector2:
        return pygame.Vector2(self.pos)

    @property
    def telegraphs(self) -> tuple[_PendingAttack, ...]:
        return tuple(self._pending)

    def phase_for_hp(self, hp: int) -> int:
        if self.max_hp <= 0:
            return 3

        clamped = max(0, min(hp, self.max_hp))
        ratio = clamped / self.max_hp
        first, second = config.BOSS_PHASE_THRESHOLDS
        if ratio > first:
            return 1
        if ratio > second:
            return 2
        return 3

    def take_damage(self, amount: int) -> bool:
        if not self.alive or amount <= 0:
            return False

        self.hp = max(0, self.hp - amount)
        target_phase = max(self.phase, self.phase_for_hp(self.hp))
        if target_phase != self.phase:
            self.phase = target_phase
            self.phase_flash = config.BOSS_PHASE_FLASH

        if self.hp == 0:
            self.alive = False
            self._pending = []
            self._refresh_telegraph()
            return True
        return False

    def update(self, dt: float, world) -> None:
        if not self.alive or dt < 0.0:
            return

        self.phase_flash = max(0.0, self.phase_flash - dt)
        self._sync_phase(world)
        self._drift(dt, world)
        self._tick_telegraphs(dt, world)
        self._tick_attack_timers(dt, world)
        self._refresh_telegraph()

    def _sync_phase(self, world) -> None:
        target_phase = max(self.phase, self.phase_for_hp(self.hp))
        if target_phase != self.phase:
            self.phase = target_phase
            self.phase_flash = config.BOSS_PHASE_FLASH

        if self.phase != self._entered_phase:
            self._enter_phase(world, self.phase)

    def _enter_phase(self, world, phase: int) -> None:
        self._entered_phase = phase
        self.aim_timer = min(
            self.aim_timer, config.BOSS_AIM_INTERVAL[phase - 1]
        )
        self.radial_timer = min(
            self.radial_timer, config.BOSS_RADIAL_INTERVAL[phase - 1]
        )
        if phase >= 2:
            self.laser_timer = config.BOSS_LASER_INTERVAL[phase - 1]
            self._summon(
                world, config.BOSS_TRANSITION_SUMMONS[phase - 1]
            )

    def _drift(self, dt: float, world) -> None:
        rect = getattr(world, "playfield_rect", None)
        if rect is None:
            rect = config.PLAYFIELD_RECT

        half = config.BOSS_SIZE / 2
        left = max(rect.left + half, rect.centerx - config.BOSS_DRIFT_RANGE)
        right = min(
            rect.right - half, rect.centerx + config.BOSS_DRIFT_RANGE
        )
        if left > right:
            left = right = rect.centerx

        self.pos.x += self.drift_direction * config.BOSS_SPEED * dt
        if self.pos.x <= left:
            self.pos.x = left
            self.drift_direction = 1
        elif self.pos.x >= right:
            self.pos.x = right
            self.drift_direction = -1

        top = rect.top + half
        bottom = rect.bottom - half
        self.pos.y = min(max(self.pos.y, top), bottom)

    def _tick_attack_timers(self, dt: float, world) -> None:
        self.aim_timer -= dt
        if self.aim_timer <= 0.0:
            self._schedule_aimed(world)
            self.aim_timer = self._retime(
                self.aim_timer, config.BOSS_AIM_INTERVAL[self.phase - 1]
            )

        self.radial_timer -= dt
        if self.radial_timer <= 0.0:
            self._schedule_radial()
            self.radial_timer = self._retime(
                self.radial_timer,
                config.BOSS_RADIAL_INTERVAL[self.phase - 1],
            )

        if self.phase >= 2:
            if self.laser_timer is None:
                self.laser_timer = config.BOSS_LASER_INTERVAL[
                    self.phase - 1
                ]
            self.laser_timer -= dt
            if self.laser_timer <= 0.0:
                self._schedule_laser(world)
                self.laser_timer = self._retime(
                    self.laser_timer,
                    config.BOSS_LASER_INTERVAL[self.phase - 1],
                )

    @staticmethod
    def _retime(timer: float, interval: float) -> float:
        timer += interval
        return timer if timer > 0.0 else interval

    def _schedule_aimed(self, world) -> None:
        self._aimed_shots += 1
        aim_base = self._aimed_shots % config.BOSS_AIM_BASE_EVERY == 0
        target = self._pick_target(world, aim_base)
        if target is None:
            target = self.center + pygame.Vector2(0, 4 * config.TILE)
        self._pending.append(
            _PendingAttack(
                "aimed", config.BOSS_AIM_TELEGRAPH, target=target
            )
        )

    def _schedule_radial(self) -> None:
        self._pending.append(
            _PendingAttack("radial", config.BOSS_RADIAL_TELEGRAPH)
        )

    def _schedule_laser(self, world) -> None:
        self._laser_shots += 1
        aim_base = self._laser_shots % config.BOSS_LASER_BASE_EVERY == 0
        target = self._pick_target(world, aim_base)
        if target is None:
            direction = config.Direction.DOWN
        else:
            delta = target - self.center
            direction = config.Direction.from_vector(delta.x, delta.y)
        self._pending.append(
            _PendingAttack(
                "laser",
                config.BOSS_LASER_TELEGRAPH,
                target=target,
                direction=direction,
            )
        )

    def _pick_target(
        self, world, prefer_base: bool = False
    ) -> pygame.Vector2 | None:
        base = getattr(world, "base", None)
        base_alive = base is not None and getattr(base, "alive", True)
        if prefer_base and base_alive:
            return pygame.Vector2(base.center)

        living = [
            player
            for player in world.players
            if getattr(player, "alive", True)
        ]
        if living:
            nearest = min(
                living,
                key=lambda player: self.pos.distance_squared_to(
                    pygame.Vector2(player.center)
                ),
            )
            return pygame.Vector2(nearest.center)

        if base_alive:
            return pygame.Vector2(base.center)
        return None

    def _tick_telegraphs(self, dt: float, world) -> None:
        remaining = []
        for attack in self._pending:
            attack.timer -= dt
            if attack.timer <= 0.0:
                self._execute(attack, world)
            else:
                remaining.append(attack)
        self._pending = remaining

    def _execute(self, attack: _PendingAttack, world) -> None:
        if attack.kind == "aimed":
            target = attack.target
            if target is None:
                target = self.center
            world.enemy_fire_at(
                self.center,
                target,
                config.BOSS_BULLET_SPEED,
                config.BOSS_BULLET_DAMAGE,
            )
        elif attack.kind == "radial":
            world.enemy_radial_burst(
                self.center,
                config.BOSS_RADIAL_COUNT[self.phase - 1],
                config.BOSS_BULLET_SPEED,
                config.BOSS_BULLET_DAMAGE,
            )
        elif attack.kind == "laser":
            direction = attack.direction or config.Direction.DOWN
            world.boss_laser(self.center, direction)

    def _refresh_telegraph(self) -> None:
        if not self._pending:
            self.telegraph = 0.0
            self.telegraph_kind = None
            self.telegraph_target = None
            self.telegraph_direction = None
            return

        first = self._pending[0]
        self.telegraph = first.timer
        self.telegraph_kind = first.kind
        self.telegraph_target = first.target
        self.telegraph_direction = first.direction

    def _summon(self, world, count: int) -> None:
        if count <= 0:
            return

        tx, ty = point_to_tile(self.pos)
        offsets = (
            (0, 2),
            (-1, 2),
            (1, 2),
            (0, 3),
            (-2, 2),
            (2, 2),
        )
        candidates = [
            (tx + dx, ty + dy)
            for dx, dy in offsets
            if in_bounds(tx + dx, ty + dy)
        ]
        if not candidates:
            return

        rng = getattr(world, "random", None)
        if rng is not None:
            rng.shuffle(candidates)

        limit = min(count, config.BOSS_MAX_SUMMONS_PER_TRANSITION)
        for tile in candidates[:limit]:
            world.spawn_enemy("tracker", tile)
