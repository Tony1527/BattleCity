from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame

_PARTICLE_LIFE_MIN = 0.25
_PARTICLE_LIFE_MAX = 0.55
_PARTICLE_SPEED_MIN = 40.0
_PARTICLE_SPEED_MAX = 160.0
_PARTICLE_SIZE = 3.0
_SHAKE_DECAY = 10.0
_SHAKE_MAX = 12.0


@dataclass
class Particle:
    pos: pygame.Vector2
    velocity: pygame.Vector2
    color: tuple[int, ...]
    life: float
    max_life: float = 0.0
    size: float = _PARTICLE_SIZE

    def __post_init__(self) -> None:
        self.pos = pygame.Vector2(self.pos)
        self.velocity = pygame.Vector2(self.velocity)
        self.color = tuple(self.color)
        if self.max_life <= 0.0:
            self.max_life = self.life
        self.life = float(self.life)
        self.max_life = float(self.max_life)
        self.size = float(self.size)


class Effects:
    def __init__(self) -> None:
        self.particles: list[Particle] = []
        self.shake_amount = 0.0

    def burst(
        self,
        pos: tuple[float, float] | pygame.Vector2,
        color: tuple[int, ...],
        count: int = 12,
    ) -> None:
        origin = pygame.Vector2(pos)
        for _ in range(max(0, int(count))):
            angle = random.uniform(0.0, math.tau)
            speed = random.uniform(_PARTICLE_SPEED_MIN, _PARTICLE_SPEED_MAX)
            life = random.uniform(_PARTICLE_LIFE_MIN, _PARTICLE_LIFE_MAX)
            velocity = pygame.Vector2(
                math.cos(angle) * speed, math.sin(angle) * speed
            )
            self.particles.append(
                Particle(origin, velocity, color, life, life)
            )

    def update(self, dt: float) -> None:
        if dt < 0.0:
            dt = 0.0
        for particle in self.particles:
            particle.life -= dt
            particle.pos += particle.velocity * dt
        self.particles = [
            particle for particle in self.particles if particle.life > 0.0
        ]
        self.shake_amount = max(0.0, self.shake_amount - _SHAKE_DECAY * dt)

    def shake(self, amount: float) -> None:
        if amount <= 0.0:
            return
        self.shake_amount = min(_SHAKE_MAX, self.shake_amount + amount)

    def offset(self) -> tuple[int, int]:
        radius = int(self.shake_amount)
        if radius <= 0:
            return (0, 0)
        return (
            random.randint(-radius, radius),
            random.randint(-radius, radius),
        )

    def draw(
        self,
        surface: pygame.Surface,
        offset: tuple[int, int] = (0, 0),
    ) -> None:
        offset_x, offset_y = offset
        for particle in self.particles:
            ratio = (
                particle.life / particle.max_life
                if particle.max_life > 0.0
                else 0.0
            )
            radius = max(1, int(particle.size * ratio))
            pygame.draw.circle(
                surface,
                particle.color,
                (
                    int(particle.pos.x) + offset_x,
                    int(particle.pos.y) + offset_y,
                ),
                radius,
            )
