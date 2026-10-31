import random

import pygame
import pytest

import config
from game import boss, entities, geometry


class FakeWorld:
    def __init__(self, players=(), base=None):
        self.players = list(players)
        self.base = base if base is not None else entities.Base()
        self.playfield_rect = pygame.Rect(config.PLAYFIELD_RECT)
        self.random = random.Random(0)
        self.aimed = []
        self.bursts = []
        self.lasers = []
        self.spawns = []
        self.damage_calls = []

    def enemy_fire_at(self, origin, target, speed, damage):
        self.aimed.append(
            (pygame.Vector2(origin), pygame.Vector2(target), speed, damage)
        )

    def enemy_radial_burst(self, origin, count, speed, damage):
        self.bursts.append(
            (pygame.Vector2(origin), count, speed, damage)
        )

    def boss_laser(self, origin, direction):
        self.lasers.append(
            (pygame.Vector2(origin), config.Direction(direction))
        )

    def spawn_enemy(self, kind, tile):
        self.spawns.append((kind, tile))
        return None

    def damage_player(self, player, amount):
        self.damage_calls.append((player, amount))


def make_player(tile=(12, 10), alive=True):
    player = entities.Player(
        0,
        geometry.tile_center(*tile),
        stats=config.PlayerStats(max_hp=100),
    )
    player.alive = alive
    return player


def damage_to_ratio(match, ratio):
    target = int(match.max_hp * ratio)
    match.take_damage(match.hp - target)
    return match


def trigger(match, world, timer_name):
    setattr(match, timer_name, 0.0)
    match.update(0.0, world)
    return match.telegraph


def test_config_has_the_pinned_boss_values():
    assert config.BOSS_HP == 360
    assert config.BOSS_SPEED == 32
    assert config.BOSS_SIZE == 96
    assert config.BOSS_PHASE_THRESHOLDS == (0.66, 0.33)


def test_boss_starts_at_full_health_in_phase_one_at_top_center():
    match = boss.Boss()

    assert match.max_hp == config.BOSS_HP
    assert match.hp == config.BOSS_HP
    assert match.alive is True
    assert match.phase == 1
    assert match.phase_flash == 0.0
    assert match.telegraph == 0.0
    assert match.pos.x == pytest.approx(config.PLAYFIELD_RECT.centerx)
    assert match.rect.size == (config.BOSS_SIZE, config.BOSS_SIZE)
    assert match.rect.center == (round(match.pos.x), round(match.pos.y))
    assert match.center == match.pos


@pytest.mark.parametrize(
    ("hp", "phase"),
    [
        (360, 1),
        (238, 1),
        (237, 2),
        (180, 2),
        (119, 2),
        (118, 3),
        (0, 3),
    ],
)
def test_phase_for_hp_uses_the_pinned_thresholds(hp, phase):
    assert boss.Boss().phase_for_hp(hp) == phase


def test_phase_never_decreases_when_health_fluctuates():
    match = boss.Boss()
    world = FakeWorld()

    damage_to_ratio(match, 0.30)
    match.update(0.0, world)
    assert match.phase == 3

    match.hp = match.max_hp
    match.update(0.0, world)

    assert match.phase_for_hp(match.hp) == 1
    assert match.phase == 3


def test_phase_transitions_flash_and_then_fade():
    match = boss.Boss()
    world = FakeWorld()

    damage_to_ratio(match, 0.60)
    assert match.phase == 2
    assert match.phase_flash > 0.0

    match.update(config.BOSS_PHASE_FLASH, world)
    assert match.phase_flash == pytest.approx(0.0)

    damage_to_ratio(match, 0.20)
    assert match.phase == 3
    assert match.phase_flash > 0.0


def test_take_damage_kills_at_zero_and_stops_all_attacks():
    match = boss.Boss()
    world = FakeWorld([make_player()])
    match.aim_timer = 0.0
    match.update(0.0, world)
    match.update(config.BOSS_AIM_TELEGRAPH, world)
    aimed_before = len(world.aimed)

    assert match.take_damage(match.max_hp) is True
    assert match.hp == 0
    assert match.alive is False
    assert match.telegraph == 0.0

    match.update(100.0, world)

    assert len(world.aimed) == aimed_before
    assert world.bursts == []
    assert world.lasers == []
    assert match.take_damage(1) is False


def test_aimed_attack_fires_at_the_nearest_player_after_a_telegraph():
    player = make_player(tile=(12, 10))
    world = FakeWorld([player])
    match = boss.Boss()

    telegraph = trigger(match, world, "aim_timer")

    assert world.aimed == []
    assert telegraph > 0.0
    assert match.telegraph_kind == "aimed"
    assert match.telegraph_target == player.center
    assert match.aim_timer == pytest.approx(config.BOSS_AIM_INTERVAL[0])

    match.update(telegraph, world)

    assert len(world.aimed) == 1
    origin, target, speed, damage = world.aimed[0]
    assert origin == match.center
    assert target == player.center
    assert speed == config.BOSS_BULLET_SPEED
    assert damage == config.BOSS_BULLET_DAMAGE


def test_aimed_attack_targets_the_base_when_no_player_is_alive():
    player = make_player(alive=False)
    world = FakeWorld([player])
    match = boss.Boss()

    telegraph = trigger(match, world, "aim_timer")
    match.update(telegraph, world)

    assert len(world.aimed) == 1
    assert world.aimed[0][1] == world.base.center


@pytest.mark.parametrize(
    ("ratio", "expected_count"),
    [(1.0, 8), (0.60, 12), (0.30, 16)],
)
def test_radial_burst_count_scales_with_phase(ratio, expected_count):
    match = boss.Boss()
    world = FakeWorld([make_player()])
    if ratio < 1.0:
        damage_to_ratio(match, ratio)
    match.update(0.0, world)
    match.aim_timer = 999.0

    telegraph = trigger(match, world, "radial_timer")

    assert world.bursts == []
    assert telegraph > 0.0
    assert match.telegraph_kind == "radial"
    assert match.radial_timer == pytest.approx(
        config.BOSS_RADIAL_INTERVAL[match.phase - 1]
    )

    match.update(telegraph, world)

    assert len(world.bursts) == 1
    origin, count, speed, damage = world.bursts[0]
    assert origin == match.center
    assert count == expected_count
    assert speed == config.BOSS_BULLET_SPEED
    assert damage == config.BOSS_BULLET_DAMAGE


def test_phase_two_laser_telegraphs_for_at_least_point_eight_seconds():
    player = make_player(tile=(12, 10))
    world = FakeWorld([player])
    match = boss.Boss()
    damage_to_ratio(match, 0.60)
    match.update(0.0, world)
    match.aim_timer = 999.0
    match.radial_timer = 999.0

    telegraph = trigger(match, world, "laser_timer")

    assert config.BOSS_LASER_TELEGRAPH >= 0.8
    assert telegraph >= 0.8
    assert match.telegraph_kind == "laser"
    assert world.lasers == []
    assert match.laser_timer == pytest.approx(config.BOSS_LASER_INTERVAL[1])

    match.update(telegraph, world)

    assert len(world.lasers) == 1
    origin, direction = world.lasers[0]
    assert origin == match.center
    assert direction == config.Direction.DOWN


def test_phase_one_never_schedules_a_laser():
    world = FakeWorld([make_player()])
    match = boss.Boss()
    match.aim_timer = 999.0
    match.radial_timer = 999.0
    match.laser_timer = 0.0

    match.update(0.0, world)
    match.update(10.0, world)

    assert world.lasers == []


def test_phase_two_entry_summons_two_trackers_only_once():
    world = FakeWorld([make_player()])
    match = boss.Boss()

    damage_to_ratio(match, 0.60)
    match.update(0.0, world)

    assert len(world.spawns) == 2
    assert [kind for kind, _ in world.spawns] == ["tracker", "tracker"]
    assert len({tile for _, tile in world.spawns}) == 2
    assert all(geometry.in_bounds(*tile) for _, tile in world.spawns)

    match.update(10.0, world)

    assert len(world.spawns) == 2


def test_phase_three_summons_no_more_than_three_per_transition():
    world = FakeWorld([make_player()])
    match = boss.Boss()
    damage_to_ratio(match, 0.60)
    match.update(0.0, world)

    damage_to_ratio(match, 0.20)
    match.update(0.0, world)

    phase_three = world.spawns[2:]
    assert len(phase_three) == 3
    assert len(phase_three) <= config.BOSS_MAX_SUMMONS_PER_TRANSITION
    assert all(kind == "tracker" for kind, _ in phase_three)
    assert all(geometry.in_bounds(*tile) for _, tile in phase_three)


def test_boss_drifts_horizontally_and_stays_inside_the_playfield():
    world = FakeWorld([make_player()])
    match = boss.Boss()
    start_x = match.pos.x
    start_y = match.pos.y
    rect = world.playfield_rect

    for _ in range(1200):
        match.update(0.05, world)
        assert rect.contains(match.rect)
        assert match.pos.y == pytest.approx(start_y)

    assert match.pos.x != start_x
    assert abs(match.pos.x - rect.centerx) <= config.BOSS_DRIFT_RANGE + 1.0
