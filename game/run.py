from __future__ import annotations

from dataclasses import dataclass

import config


@dataclass
class RunState:
    run_seed: int
    difficulty: str
    language: str
    level_index: int
    player_stats: list[config.PlayerStats]
    upgrade_levels: list[dict[str, int]]
