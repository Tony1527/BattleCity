from __future__ import annotations

from dataclasses import dataclass
import random

from config import PlayerStats


@dataclass(frozen=True)
class Upgrade:
    id: str
    name_key: str
    desc_key: str
    stat: str
    op: str
    amount: float
    max_stacks: int
    roles: frozenset[str] = frozenset({"p1", "p2"})


UPGRADE_POOL: tuple[Upgrade, ...] = (
    Upgrade(
        "overclock",
        "upgrade.overclock.name",
        "upgrade.overclock.desc",
        "fire_interval",
        "mul",
        0.85,
        3,
    ),
    Upgrade(
        "heavy_rounds",
        "upgrade.heavy_rounds.name",
        "upgrade.heavy_rounds.desc",
        "bullet_damage",
        "add",
        1,
        3,
    ),
    Upgrade(
        "servos",
        "upgrade.servos.name",
        "upgrade.servos.desc",
        "speed",
        "mul",
        1.12,
        3,
    ),
    Upgrade(
        "plated_hull",
        "upgrade.plated_hull.name",
        "upgrade.plated_hull.desc",
        "max_hp",
        "add",
        1,
        3,
    ),
    Upgrade(
        "reactive_armor",
        "upgrade.reactive_armor.name",
        "upgrade.reactive_armor.desc",
        "reactive_armor_stacks",
        "add",
        1,
        7,
    ),
    Upgrade(
        "rapid_loader",
        "upgrade.rapid_loader.name",
        "upgrade.rapid_loader.desc",
        "bullet_speed",
        "mul",
        1.15,
        3,
    ),
    Upgrade(
        "grenade_tuning",
        "upgrade.grenade_tuning.name",
        "upgrade.grenade_tuning.desc",
        "grenade_cooldown",
        "mul",
        0.85,
        3,
        frozenset({"p1"}),
    ),
    Upgrade(
        "demo_charge",
        "upgrade.demo_charge.name",
        "upgrade.demo_charge.desc",
        "grenade_damage",
        "add",
        10,
        3,
        frozenset({"p1"}),
    ),
    Upgrade(
        "wide_blast",
        "upgrade.wide_blast.name",
        "upgrade.wide_blast.desc",
        "grenade_radius",
        "mul",
        1.15,
        3,
        frozenset({"p1"}),
    ),
    Upgrade(
        "split_charge",
        "upgrade.split_charge.name",
        "upgrade.split_charge.desc",
        "grenade_split",
        "add",
        1,
        2,
        frozenset({"p1"}),
    ),
    Upgrade(
        "laser_focus",
        "upgrade.laser_focus.name",
        "upgrade.laser_focus.desc",
        "laser_damage",
        "add",
        15,
        3,
        frozenset({"p2"}),
    ),
    Upgrade(
        "laser_capacitor",
        "upgrade.laser_capacitor.name",
        "upgrade.laser_capacitor.desc",
        "laser_cooldown",
        "mul",
        0.85,
        3,
        frozenset({"p2"}),
    ),
    Upgrade(
        "laser_extender",
        "upgrade.laser_extender.name",
        "upgrade.laser_extender.desc",
        "laser_range",
        "mul",
        1.15,
        3,
        frozenset({"p2"}),
    ),
    Upgrade(
        "base_shield",
        "upgrade.base_shield.name",
        "upgrade.base_shield.desc",
        "base_shield",
        "add",
        1,
        2,
    ),
)

_BY_ID = {upgrade.id: upgrade for upgrade in UPGRADE_POOL}


def upgrade_by_id(upgrade_id: str) -> Upgrade:
    return _BY_ID[upgrade_id]


def roll_upgrades(
    rng: random.Random,
    levels: dict[str, int],
    count: int = 3,
    role: str | None = None,
) -> list[Upgrade]:
    available = [
        upgrade
        for upgrade in UPGRADE_POOL
        if levels.get(upgrade.id, 0) < upgrade.max_stacks
        and (role is None or role in upgrade.roles)
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
