from __future__ import annotations

from dataclasses import dataclass
import random

from config import PlayerStats


@dataclass(frozen=True)
class Upgrade:
    id: str
    name: str
    description: str
    stat: str
    op: str
    amount: float
    max_stacks: int


UPGRADE_POOL: tuple[Upgrade, ...] = (
    Upgrade(
        "overclock",
        "Overclock",
        "Fire normal rounds 15% faster.",
        "fire_interval",
        "mul",
        0.85,
        3,
    ),
    Upgrade(
        "heavy_rounds",
        "Heavy Rounds",
        "Normal rounds deal +1 damage.",
        "bullet_damage",
        "add",
        1,
        3,
    ),
    Upgrade(
        "servos",
        "Servos",
        "Move 12% faster.",
        "speed",
        "mul",
        1.12,
        3,
    ),
    Upgrade(
        "plated_hull",
        "Plated Hull",
        "Gain +1 maximum HP.",
        "max_hp",
        "add",
        1,
        3,
    ),
    Upgrade(
        "reactive_armor",
        "Reactive Armor",
        "Reduce incoming damage by 5%.",
        "damage_reduction",
        "add",
        0.05,
        3,
    ),
    Upgrade(
        "rapid_loader",
        "Rapid Loader",
        "Normal rounds travel 15% faster.",
        "bullet_speed",
        "mul",
        1.15,
        3,
    ),
    Upgrade(
        "grenade_tuning",
        "Grenade Tuning",
        "Grenade cooldown reduced by 15%.",
        "grenade_cooldown",
        "mul",
        0.85,
        3,
    ),
    Upgrade(
        "demo_charge",
        "Demo Charge",
        "Grenades deal +10 damage.",
        "grenade_damage",
        "add",
        10,
        3,
    ),
    Upgrade(
        "wide_blast",
        "Wide Blast",
        "Grenade radius increased by 15%.",
        "grenade_radius",
        "mul",
        1.15,
        3,
    ),
    Upgrade(
        "split_charge",
        "Split Charge",
        "Grenades split into an extra explosion.",
        "grenade_split",
        "add",
        1,
        2,
    ),
    Upgrade(
        "laser_focus",
        "Laser Focus",
        "Laser deals +15 damage.",
        "laser_damage",
        "add",
        15,
        3,
    ),
    Upgrade(
        "laser_capacitor",
        "Laser Capacitor",
        "Laser cooldown reduced by 15%.",
        "laser_cooldown",
        "mul",
        0.85,
        3,
    ),
    Upgrade(
        "laser_extender",
        "Laser Extender",
        "Laser range increased by 15%.",
        "laser_range",
        "mul",
        1.15,
        3,
    ),
    Upgrade(
        "prism",
        "Prism",
        "Laser reflects off steel once per stack.",
        "laser_reflect",
        "add",
        1,
        2,
    ),
    Upgrade(
        "base_shield",
        "Base Shield",
        "Base absorbs +1 damage each level.",
        "base_shield",
        "add",
        1,
        2,
    ),
    Upgrade(
        "spare_parts",
        "Spare Parts",
        "Gain +1 shared revive.",
        "extra_lives",
        "add",
        1,
        2,
    ),
)

_BY_ID = {upgrade.id: upgrade for upgrade in UPGRADE_POOL}


def upgrade_by_id(upgrade_id: str) -> Upgrade:
    return _BY_ID[upgrade_id]


def roll_upgrades(
    rng: random.Random, levels: dict[str, int], count: int = 3
) -> list[Upgrade]:
    available = [
        upgrade
        for upgrade in UPGRADE_POOL
        if levels.get(upgrade.id, 0) < upgrade.max_stacks
    ]
    return rng.sample(available, min(count, len(available)))


def apply_upgrade(
    stats: PlayerStats, levels: dict[str, int], upgrade_id: str
) -> bool:
    upgrade = upgrade_by_id(upgrade_id)
    stacks = levels.get(upgrade.id, 0)
    if stacks >= upgrade.max_stacks:
        return False

    current = getattr(stats, upgrade.stat)
    if upgrade.op == "mul":
        setattr(stats, upgrade.stat, current * upgrade.amount)
    else:
        setattr(stats, upgrade.stat, current + upgrade.amount)
    levels[upgrade.id] = stacks + 1
    return True
