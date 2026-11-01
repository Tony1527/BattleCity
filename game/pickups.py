from __future__ import annotations

import random
from dataclasses import dataclass

import pygame

import config

PICKUP_KINDS = tuple(config.ITEM_WEIGHTS)


def roll_pickup_kind(rng: random.Random) -> str:
    kinds = list(config.ITEM_WEIGHTS)
    weights = [config.ITEM_WEIGHTS[kind] for kind in kinds]
    return rng.choices(kinds, weights=weights, k=1)[0]


@dataclass
class Pickup:
    kind: str
    pos: pygame.Vector2
    ttl: float = config.ITEM_TTL

    def __post_init__(self) -> None:
        self.pos = pygame.Vector2(self.pos)

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(
            round(self.pos.x - config.ITEM_SIZE / 2),
            round(self.pos.y - config.ITEM_SIZE / 2),
            config.ITEM_SIZE,
            config.ITEM_SIZE,
        )

    def update(self, dt: float) -> bool:
        if dt > 0.0:
            self.ttl = max(0.0, self.ttl - dt)
        return self.ttl > 0.0
