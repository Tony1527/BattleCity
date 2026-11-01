from __future__ import annotations

from dataclasses import dataclass

import config


@dataclass
class Trap:
    tile: tuple[int, int]
    cooldown: float = 0.0
    armed: bool = True

    def update(self, dt: float) -> None:
        if dt > 0.0 and self.cooldown > 0.0:
            self.cooldown = max(0.0, self.cooldown - dt)
        self.armed = self.cooldown <= 0.0

    def try_trigger(self) -> bool:
        if not self.armed or self.cooldown > 0.0:
            return False
        self.armed = False
        self.cooldown = config.TRAP_REARM_TIME
        return True
