from __future__ import annotations

import math
from dataclasses import dataclass, replace

import config


@dataclass(frozen=True)
class DifficultyProfile:
    key: str
    enemy_hp_mult: float
    enemy_fire_interval_mult: float
    enemy_attack_range_mult: float
    spawn_interval_mult: float
    base_hp: int
    boss_hp_mult: float
    boss_interval_mult: float
    elite_hp_mult: float
    elite_shield_mult: float


NORMAL = DifficultyProfile(
    key="normal",
    enemy_hp_mult=1.0,
    enemy_fire_interval_mult=1.0,
    enemy_attack_range_mult=1.0,
    spawn_interval_mult=1.0,
    base_hp=config.BASE_HP_NORMAL,
    boss_hp_mult=1.0,
    boss_interval_mult=1.0,
    elite_hp_mult=1.0,
    elite_shield_mult=1.0,
)

HELL = DifficultyProfile(
    key="hell",
    enemy_hp_mult=1.5,
    enemy_fire_interval_mult=0.8,
    enemy_attack_range_mult=1.15,
    spawn_interval_mult=0.8,
    base_hp=config.BASE_HP_HELL,
    boss_hp_mult=1.5,
    boss_interval_mult=0.85,
    elite_hp_mult=1.5,
    elite_shield_mult=1.5,
)

PROFILES = {profile.key: profile for profile in (NORMAL, HELL)}


def get_profile(key: str) -> DifficultyProfile:
    return PROFILES[key]


def scaled_enemy_spec(
    kind: str, profile: DifficultyProfile
) -> config.EnemySpec:
    base = config.ENEMY_SPECS[kind]
    return replace(
        base,
        hp=math.ceil(base.hp * profile.enemy_hp_mult),
        fire_interval=base.fire_interval
        * profile.enemy_fire_interval_mult,
        attack_range=base.attack_range * profile.enemy_attack_range_mult,
    )
