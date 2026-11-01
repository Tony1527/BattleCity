from dataclasses import FrozenInstanceError, fields
import random

import pytest

import config
from game import upgrades


def test_pool_ids_are_unique_and_cover_required_upgrades():
    ids = [upgrade.id for upgrade in upgrades.UPGRADE_POOL]
    assert len(upgrades.UPGRADE_POOL) >= 15
    assert len(set(ids)) == len(ids)
    assert set(ids) == {
        "overclock",
        "heavy_rounds",
        "servos",
        "plated_hull",
        "reactive_armor",
        "rapid_loader",
        "grenade_tuning",
        "demo_charge",
        "wide_blast",
        "split_charge",
        "laser_focus",
        "laser_capacitor",
        "laser_extender",
        "base_shield",
        "spare_parts",
    }


def test_upgrade_dataclass_is_frozen_and_well_formed():
    upgrade = upgrades.upgrade_by_id("overclock")
    assert isinstance(upgrade, upgrades.Upgrade)
    assert [field.name for field in fields(upgrade)] == [
        "id",
        "name",
        "description",
        "stat",
        "op",
        "amount",
        "max_stacks",
        "roles",
    ]
    with pytest.raises(FrozenInstanceError):
        upgrade.amount = 1.0
    stat_names = set(config.PlayerStats.__dataclass_fields__)
    for entry in upgrades.UPGRADE_POOL:
        assert entry.op in ("add", "mul")
        assert entry.stat in stat_names
        assert entry.max_stacks >= 2
        assert 2 <= entry.max_stacks <= 4
        assert entry.roles
        assert entry.roles <= frozenset({"p1", "p2"})


def test_upgrade_by_id_round_trips_and_rejects_unknown():
    for upgrade in upgrades.UPGRADE_POOL:
        assert upgrades.upgrade_by_id(upgrade.id) is upgrade
    with pytest.raises(KeyError):
        upgrades.upgrade_by_id("does-not-exist")


def test_roll_upgrades_never_repeats_or_offers_capped_entries():
    levels = {"overclock": 3, "split_charge": 2}
    rng = random.Random(7)
    for _ in range(50):
        offers = upgrades.roll_upgrades(rng, levels, count=3)
        ids = [upgrade.id for upgrade in offers]
        assert len(ids) == len(set(ids))
        assert "overclock" not in ids
        assert "split_charge" not in ids
        assert all(levels.get(uid, 0) < upgrades.upgrade_by_id(uid).max_stacks for uid in ids)


def test_roll_upgrades_returns_only_available_count():
    levels = {
        upgrade.id: upgrade.max_stacks
        for upgrade in upgrades.UPGRADE_POOL
    }
    levels["spare_parts"] = (
        upgrades.upgrade_by_id("spare_parts").max_stacks - 1
    )
    offers = upgrades.roll_upgrades(random.Random(1), levels, count=3)
    assert [upgrade.id for upgrade in offers] == ["spare_parts"]


def test_fire_interval_multiplier_caps_after_three_stacks():
    stats = config.PlayerStats()
    levels = {}
    overclock = upgrades.upgrade_by_id("overclock")
    assert overclock.stat == "fire_interval"
    assert overclock.op == "mul"
    assert overclock.max_stacks == 3

    for _ in range(overclock.max_stacks):
        assert upgrades.apply_upgrade(stats, levels, "overclock") is True
    assert levels["overclock"] == 3
    assert stats.fire_interval == pytest.approx(0.35 * 0.85**3)

    before = stats.clone()
    assert upgrades.apply_upgrade(stats, levels, "overclock") is False
    assert levels["overclock"] == 3
    assert stats == before


def test_max_hp_add_increases_health():
    stats = config.PlayerStats()
    levels = {}
    plated_hull = upgrades.upgrade_by_id("plated_hull")
    assert plated_hull.stat == "max_hp"
    assert plated_hull.op == "add"
    assert upgrades.apply_upgrade(stats, levels, "plated_hull") is True
    assert stats.max_hp == config.PlayerStats().max_hp + plated_hull.amount
    assert levels == {"plated_hull": 1}


def test_special_affix_caps_are_obeyed():
    stats = config.PlayerStats()
    levels = {}

    for _ in range(upgrades.upgrade_by_id("split_charge").max_stacks):
        assert upgrades.apply_upgrade(stats, levels, "split_charge") is True
    split_cap = stats.grenade_split
    assert split_cap == upgrades.upgrade_by_id("split_charge").max_stacks
    assert upgrades.apply_upgrade(stats, levels, "split_charge") is False
    assert stats.grenade_split == split_cap

    assert "prism" not in {
        upgrade.id for upgrade in upgrades.UPGRADE_POOL
    }
    assert "laser_reflect" in config.PlayerStats.__dataclass_fields__


def test_apply_upgrade_does_not_mutate_levels_on_failure():
    stats = config.PlayerStats()
    levels = {"servos": upgrades.upgrade_by_id("servos").max_stacks}
    before_stats = stats.clone()
    before_levels = dict(levels)
    assert upgrades.apply_upgrade(stats, levels, "servos") is False
    assert stats == before_stats
    assert levels == before_levels


def test_role_restricted_upgrades_are_tagged_for_the_right_player():
    grenade_ids = {
        "grenade_tuning",
        "demo_charge",
        "wide_blast",
        "split_charge",
    }
    laser_ids = {
        "laser_focus",
        "laser_capacitor",
        "laser_extender",
    }
    for uid in grenade_ids:
        assert upgrades.upgrade_by_id(uid).roles == frozenset({"p1"})
    for uid in laser_ids:
        assert upgrades.upgrade_by_id(uid).roles == frozenset({"p2"})


def test_roll_upgrades_filters_offers_by_player_role():
    rng = random.Random(11)
    grenade_ids = {
        "grenade_tuning",
        "demo_charge",
        "wide_blast",
        "split_charge",
    }
    laser_ids = {
        "laser_focus",
        "laser_capacitor",
        "laser_extender",
    }
    for _ in range(100):
        p1_offers = upgrades.roll_upgrades(rng, {}, 3, role="p1")
        p2_offers = upgrades.roll_upgrades(rng, {}, 3, role="p2")
        assert len(p1_offers) == 3
        assert len(p2_offers) == 3
        assert not ({offer.id for offer in p1_offers} & laser_ids)
        assert not ({offer.id for offer in p2_offers} & grenade_ids)

    shared = upgrades.roll_upgrades(rng, {}, 50)
    assert {offer.id for offer in shared} == {
        upgrade.id for upgrade in upgrades.UPGRADE_POOL
    }
