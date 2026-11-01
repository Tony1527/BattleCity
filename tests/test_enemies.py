import random

import pygame
import pytest

import config
from game import enemies, entities, geometry
from game.world import World


class FakeWorld:
    def __init__(
        self,
        players=(),
        bricks=(),
        steel=(),
        path=None,
        base_entrances=None,
    ):
        self.players = list(players)
        self.bricks = set(bricks)
        self.steel = set(steel)
        self.path = None if path is None else list(path)
        self.base_entrances = tuple(
            config.BASE_ENTRANCES
            if base_entrances is None
            else base_entrances
        )
        self.moves = []
        self.shots = []
        self.blasts = []
        self.spawns = []
        self.spawned = []
        self.damage_calls = []
        self.random = random.Random(0)

    def point_to_tile(self, pos):
        return geometry.point_to_tile(pos)

    def tile_center(self, tx, ty):
        return geometry.tile_center(tx, ty)

    def is_brick(self, tx, ty):
        return (tx, ty) in self.bricks

    def is_steel(self, tx, ty):
        return (tx, ty) in self.steel

    def find_path(self, start, goal):
        if self.path is not None:
            return list(self.path)
        if start == goal:
            return [start]
        return [start, goal]

    def move_enemy(self, enemy, direction, dt):
        self.moves.append((enemy, config.Direction(direction), dt))
        dx, dy = config.Direction(direction).vector
        enemy.pos += pygame.Vector2(dx, dy) * enemy.speed * dt
        return True

    def enemy_fire(self, enemy, direction):
        self.shots.append((enemy, config.Direction(direction)))

    def demolisher_blast(self, enemy):
        self.blasts.append(enemy)

    def spawn_enemy(self, kind, tile):
        self.spawns.append((kind, tile))
        enemy = enemies.make_enemy(kind, tile)
        self.spawned.append(enemy)
        return enemy

    def damage_player(self, player, amount):
        self.damage_calls.append((player, amount))
        player.take_damage(amount)


def make_player(tile=(5, 5)):
    stats = config.PlayerStats(max_hp=100)
    player = entities.Player(0, geometry.tile_center(*tile), stats=stats)
    player.hp = stats.max_hp
    return player


def ring_tiles(center, min_radius, max_radius):
    tiles = set()
    for radius in range(min_radius, max_radius + 1):
        for dx in range(-radius, radius + 1):
            dy = radius - abs(dx)
            for offset_y in (dy, -dy):
                tiles.add((center[0] + dx, center[1] + offset_y))
    return tiles


@pytest.mark.parametrize("kind", ["tracker", "gunner", "demolisher"])
def test_make_enemy_builds_configured_specs(kind):
    enemy = enemies.make_enemy(kind, (4, 5))
    spec = config.ENEMY_SPECS[kind]

    assert enemy.kind == kind
    assert enemy.pos == geometry.tile_center(4, 5)
    assert enemy.center == enemy.pos
    assert enemy.hp == spec.hp
    assert enemy.max_hp == spec.hp
    assert enemy.speed == spec.speed
    assert enemy.direction == config.Direction.UP
    assert enemy.fire_timer == 0
    assert enemy.alive is True
    assert enemy.rect.size == (config.ENEMY_SIZE, config.ENEMY_SIZE)
    assert enemy.rect.center == (enemy.pos.x, enemy.pos.y)


def test_make_enemy_returns_elite_with_gunner_stats_and_elite_timers():
    elite = enemies.make_enemy("elite", (4, 5))

    assert isinstance(elite, enemies.EliteEnemy)
    assert elite.kind == "elite"
    assert elite.max_hp == config.ELITE_HP_BASE
    assert elite.speed == config.ENEMY_SPECS["gunner"].speed
    assert elite.shield == config.ELITE_SHIELD_BASE
    assert elite.shield_timer == pytest.approx(config.ELITE_SHIELD_REGEN)
    assert elite.summon_timer == pytest.approx(config.ELITE_SUMMON_INTERVAL)


def test_make_enemy_scales_elite_health_and_shield_per_level():
    elite = enemies.make_enemy(
        "elite",
        (4, 5),
        elite_level=3,
        elite_hp_mult=1.5,
        elite_shield_mult=1.5,
    )

    assert elite.max_hp == 6
    assert elite.hp == 6
    assert elite.max_shield == 23
    assert elite.shield == 23


def test_make_enemy_uses_the_supplied_elite_gunner_spec():
    spec = config.ENEMY_SPECS["gunner"]
    scaled = config.EnemySpec(
        spec.kind,
        spec.hp,
        spec.speed,
        spec.fire_interval * 0.8,
        spec.bullet_speed,
        spec.bullet_damage,
        spec.attack_range * 1.15,
        spec.score,
    )
    elite = enemies.make_enemy("elite", (4, 5), spec=scaled)

    assert elite.spec is scaled
    assert elite.spec.fire_interval == pytest.approx(1.52)
    assert elite.spec.attack_range == pytest.approx(441.6)


def test_take_damage_kills_and_sets_alive_false():
    enemy = enemies.make_enemy("tracker", (4, 5))
    world = FakeWorld()

    assert enemy.take_damage(1, world) is False
    assert enemy.hp == 1
    assert enemy.alive is True

    assert enemy.take_damage(1, world) is True
    assert enemy.hp == 0
    assert enemy.alive is False

    assert enemy.take_damage(5, world) is False
    assert enemy.hp == 0
    assert enemy.alive is False


def test_elite_shield_absorbs_damage_before_health():
    elite = enemies.make_enemy("elite", (4, 5))
    world = FakeWorld()

    assert elite.take_damage(5, world) is False
    assert elite.shield == config.ELITE_SHIELD_BASE - 5
    assert elite.hp == elite.max_hp

    assert elite.take_damage(20, world) is True
    assert elite.shield == 0
    assert elite.hp == 0
    assert elite.alive is False


def test_elite_regenerates_shield_on_timer_without_exceeding_cap():
    elite = enemies.make_enemy("elite", (4, 5))
    world = FakeWorld()
    elite.shield = config.ELITE_SHIELD_BASE - 1
    elite.shield_timer = config.ELITE_SHIELD_REGEN

    elite.update(config.ELITE_SHIELD_REGEN, world)
    assert elite.shield == config.ELITE_SHIELD_BASE

    elite.shield_timer = config.ELITE_SHIELD_REGEN
    elite.update(config.ELITE_SHIELD_REGEN * 10, world)
    assert elite.shield == config.ELITE_SHIELD_BASE


def test_elite_summons_one_tracker_and_never_more_than_cap_alive():
    elite = enemies.make_enemy("elite", (4, 5))
    world = FakeWorld()

    elite.update(config.ELITE_SUMMON_INTERVAL, world)

    assert len(world.spawns) == config.ELITE_MAX_SUMMONS
    assert [kind for kind, _ in world.spawns] == ["tracker"]
    assert all(enemy.alive for enemy in world.spawned)

    elite.update(config.ELITE_SUMMON_INTERVAL, world)
    assert len(world.spawns) == config.ELITE_MAX_SUMMONS

    world.spawned[0].alive = False
    elite.update(config.ELITE_SUMMON_INTERVAL, world)
    assert len(world.spawns) == config.ELITE_MAX_SUMMONS + 1
    assert sum(enemy.alive for enemy in world.spawned) == config.ELITE_MAX_SUMMONS


def test_tracker_fires_at_base_when_the_line_of_sight_is_clear():
    world = FakeWorld()
    tracker = enemies.make_enemy("tracker", (11, 7))

    tracker.update(0.1, world)

    assert world.shots == [(tracker, config.Direction.DOWN)]
    assert tracker.fire_timer == pytest.approx(
        config.ENEMY_SPECS["tracker"].fire_interval
    )


def test_tracker_does_not_fire_at_base_through_a_brick():
    world = FakeWorld(bricks={(11, 9)})
    tracker = enemies.make_enemy("tracker", (11, 7))

    tracker.update(0.1, world)

    assert world.shots == []


def test_tracker_does_not_fire_at_base_through_steel():
    world = FakeWorld(steel={(11, 9)})
    tracker = enemies.make_enemy("tracker", (11, 7))

    tracker.update(0.1, world)

    assert world.shots == []


def test_tracker_fires_at_a_blocking_brick_on_its_path():
    path = [(11, 5), (11, 6), (11, 7), (11, 8), (11, 9), (11, 10)]
    world = FakeWorld(path=path, bricks={(11, 6)})
    tracker = enemies.make_enemy("tracker", (11, 5))

    tracker.update(0.1, world)

    assert world.shots == [(tracker, config.Direction.DOWN)]
    assert tracker.fire_timer == pytest.approx(
        config.ENEMY_SPECS["tracker"].fire_interval
    )


def test_demolisher_telegraphs_then_blasts_a_nearby_player():
    player = make_player(tile=(11, 10))
    world = FakeWorld(players=[player])
    demolisher = enemies.make_enemy("demolisher", (11, 9))

    demolisher.update(config.DEMOLISHER_TELEGRAPH / 2, world)
    assert world.blasts == []

    demolisher.update(config.DEMOLISHER_TELEGRAPH / 2, world)
    assert world.blasts == [demolisher]
    assert demolisher.alive is False

    demolisher.update(config.DEMOLISHER_TELEGRAPH, world)
    assert world.blasts == [demolisher]


def test_demolisher_blasts_when_within_range_of_a_base_entrance():
    world = FakeWorld(base_entrances=((5, 5),))
    demolisher = enemies.make_enemy("demolisher", (5, 5))

    demolisher.update(config.DEMOLISHER_TELEGRAPH, world)

    assert world.blasts == [demolisher]
    assert demolisher.alive is False

    demolisher.update(config.DEMOLISHER_TELEGRAPH, world)
    assert world.blasts == [demolisher]


def test_demolisher_fires_at_blocking_bricks_twice_as_fast():
    path = [(11, 5), (11, 6), (11, 7), (11, 8), (11, 9), (11, 10)]
    world = FakeWorld(path=path, bricks={(11, 6)})
    demolisher = enemies.make_enemy("demolisher", (11, 5))

    demolisher.update(0.1, world)

    assert world.shots == [(demolisher, config.Direction.DOWN)]
    assert demolisher.fire_timer == pytest.approx(
        config.ENEMY_SPECS["demolisher"].fire_interval / 2
    )


def test_gunner_stops_and_fires_when_player_is_in_line_and_in_range():
    player = make_player(tile=(5, 7))
    world = FakeWorld(players=[player])
    gunner = enemies.make_enemy("gunner", (5, 5))

    gunner.update(0.1, world)

    assert world.shots == [(gunner, config.Direction.DOWN)]
    assert world.moves == []


def test_gunner_repositions_when_player_is_out_of_attack_range():
    player = make_player(tile=(5, 14))
    world = FakeWorld(players=[player])
    gunner = enemies.make_enemy("gunner", (5, 5))

    gunner.update(0.1, world)

    assert world.shots == []
    assert world.moves


def test_gunner_targets_the_base_when_no_player_is_alive():
    player = make_player(tile=(5, 7))
    player.alive = False
    world = FakeWorld(players=[player])
    gunner = enemies.make_enemy("gunner", (11, 5))

    gunner.update(0.1, world)

    assert world.shots == [(gunner, config.Direction.DOWN)]


def test_elite_telegraphs_then_fires_a_three_shot_spread():
    player = make_player(tile=(5, 7))
    world = FakeWorld(players=[player])
    elite = enemies.make_enemy("elite", (5, 5))

    elite.update(0.1, world)

    assert world.shots == []
    assert elite.telegraph == pytest.approx(config.ELITE_TELEGRAPH)
    assert elite.pending_spread == config.Direction.DOWN

    elite.update(config.ELITE_TELEGRAPH - 0.1, world)
    assert world.shots == []
    assert elite.telegraph == pytest.approx(0.1)

    elite.update(0.11, world)

    directions = [direction for _, direction in world.shots]
    assert len(directions) == config.ELITE_SPREAD_SHOTS
    assert set(directions) == {
        config.Direction.RIGHT,
        config.Direction.DOWN,
        config.Direction.LEFT,
    }
    assert elite.pending_spread is None
    assert (
        0.0
        < elite.fire_timer
        <= config.ENEMY_SPECS["gunner"].fire_interval
    )


def test_follow_path_returns_next_direction_and_snaps_to_tile_center():
    world = FakeWorld()
    enemy = enemies.make_enemy("tracker", (2, 2))
    center = geometry.tile_center(2, 2)
    enemy.pos = pygame.Vector2(center.x + 5, center.y + 7)

    direction = enemies.follow_path(enemy, world, [(2, 2), (3, 2)], 0.1)

    assert direction == config.Direction.RIGHT
    assert enemy.pos.y == center.y
    assert world.moves == [(enemy, config.Direction.RIGHT, 0.1)]


def test_follow_path_snaps_the_other_axis_for_vertical_movement():
    world = FakeWorld()
    enemy = enemies.make_enemy("tracker", (2, 2))
    center = geometry.tile_center(2, 2)
    enemy.pos = pygame.Vector2(center.x + 9, center.y - 4)

    direction = enemies.follow_path(enemy, world, [(2, 2), (2, 1)], 0.1)

    assert direction == config.Direction.UP
    assert enemy.pos.x == center.x


def test_follow_path_returns_none_for_empty_or_finished_paths():
    world = FakeWorld()
    enemy = enemies.make_enemy("tracker", (2, 2))

    assert enemies.follow_path(enemy, world, [], 0.1) is None
    assert enemies.follow_path(enemy, world, [(2, 2)], 0.1) is None
    assert world.moves == []


def test_gunner_targets_the_nearest_living_player():
    near = make_player(tile=(6, 5))
    far = make_player(tile=(5, 9))
    world = FakeWorld(players=[far, near])
    gunner = enemies.make_enemy("gunner", (5, 5))

    gunner.update(0.1, world)

    assert world.shots == [(gunner, config.Direction.RIGHT)]


def test_follow_path_returns_none_when_current_tile_is_the_last_waypoint():
    world = FakeWorld()
    enemy = enemies.make_enemy("tracker", (3, 2))

    assert enemies.follow_path(enemy, world, [(2, 2), (3, 2)], 0.1) is None
    assert world.moves == []


def test_make_enemy_rejects_unknown_kind():
    with pytest.raises(ValueError):
        enemies.make_enemy("unknown", (0, 0))


def test_dead_enemy_update_does_nothing():
    world = FakeWorld()
    tracker = enemies.make_enemy("tracker", (11, 7))
    tracker.alive = False

    tracker.update(1.0, world)

    assert world.shots == []
    assert world.moves == []
    assert tracker.fire_timer == 0.0


def test_fire_timer_suppresses_an_immediate_second_shot():
    world = FakeWorld()
    tracker = enemies.make_enemy("tracker", (11, 7))

    tracker.update(0.1, world)
    assert len(world.shots) == 1

    tracker.update(0.1, world)
    assert len(world.shots) == 1


def test_elite_shield_timer_resets_only_when_shield_absorbs_damage():
    elite = enemies.make_enemy("elite", (4, 5))
    world = FakeWorld()

    elite.shield = 0
    elite.shield_timer = 1.0
    assert elite.take_damage(1, world) is False
    assert elite.shield_timer == 1.0

    elite.shield = 2
    elite.shield_timer = 1.0
    assert elite.take_damage(1, world) is False
    assert elite.shield_timer == config.ELITE_SHIELD_REGEN


@pytest.mark.parametrize(
    ("kind", "tile", "expected"),
    [
        ("tracker", (10, 11), config.Direction.RIGHT),
        ("gunner", (13, 11), config.Direction.LEFT),
    ],
)
def test_base_targeting_from_side_entrances_aims_at_a_base_tile(
    kind, tile, expected
):
    world = FakeWorld()
    enemy = enemies.make_enemy(kind, tile)

    enemy.update(0.1, world)

    assert world.shots == [(enemy, expected)]


@pytest.mark.parametrize("kind", ["gunner", "elite"])
def test_gunner_repositions_from_a_diagonal_ring_tile(kind):
    player = make_player(tile=(2, 2))
    world = FakeWorld(players=[player], bricks={(4, 4)})
    enemy = enemies.make_enemy(kind, (5, 5))

    enemy.update(0.1, world)

    assert world.shots == []
    assert world.moves


@pytest.mark.parametrize("kind", ["gunner", "elite"])
def test_gunner_repositions_from_a_brick_blocked_ring_tile(kind):
    player = make_player(tile=(5, 0))
    world = FakeWorld(players=[player], bricks={(5, 2)})
    enemy = enemies.make_enemy(kind, (5, 5))

    enemy.update(0.1, world)

    assert world.shots == []
    assert world.moves


def test_elite_summons_never_target_steel_tiles():
    elite = enemies.make_enemy("elite", (4, 5))
    world = FakeWorld(
        steel={(4, 4), (5, 5), (4, 6), (3, 5)}
    )
    elite.summon_timer = 0.0

    elite.update(0.0, world)

    assert len(world.spawns) == config.ELITE_MAX_SUMMONS
    assert all(tile not in world.steel for _, tile in world.spawns)


@pytest.mark.parametrize("kind", ["gunner", "elite"])
def test_gunner_does_not_freeze_when_current_tile_is_the_only_ring_goal(
    kind,
):
    player = make_player(tile=(5, 5))
    current = (5, 9)
    steel = ring_tiles(
        (5, 5),
        config.GUNNER_PREFERRED_MIN,
        config.GUNNER_PREFERRED_MAX,
    )
    steel.discard(current)
    world = FakeWorld(players=[player], bricks={(5, 7)}, steel=steel)
    enemy = enemies.make_enemy(kind, current)
    start = pygame.Vector2(enemy.pos)

    enemy.update(0.1, world)

    assert world.shots == []
    assert world.moves
    assert enemy.direction == config.Direction.UP
    assert enemy.pos.y < start.y


@pytest.mark.parametrize("kind", ["gunner", "elite"])
def test_gunner_adjacent_fallback_uses_an_adjacent_tile(kind):
    player = make_player(tile=(5, 5))
    current = (7, 7)
    steel = ring_tiles(
        (5, 5),
        config.GUNNER_PREFERRED_MIN,
        config.GUNNER_PREFERRED_MAX,
    )
    steel.discard(current)
    steel.update({(7, 6), (6, 6)})
    world = FakeWorld(players=[player], steel=steel)
    enemy = enemies.make_enemy(kind, current)
    start = pygame.Vector2(enemy.pos)

    enemy.update(0.1, world)

    assert world.shots == []
    assert world.moves
    assert enemy.direction == config.Direction.LEFT
    assert enemy.pos.x < start.x


def test_gunner_fires_at_a_brick_blocking_its_reposition_path():
    world = World(0, seed=3)
    world.grid = [
        [config.Tile.EMPTY for _ in range(config.GRID_COLS)]
        for _ in range(config.GRID_ROWS)
    ]
    world.level.grid = world.grid
    world.quota_remaining = 0
    world.spawn_quota = 0
    world.spawn_timer = float("inf")
    world.max_active = 0
    world.base.reset_for_level(shield=10_000)
    world.players[1].alive = False
    world.players[1].eliminated = True
    world.players[0].pos = geometry.tile_center(5, 9)
    world.grid[6][5] = config.Tile.BRICK
    world.grid[5][4] = config.Tile.BRICK
    gunner = enemies.make_enemy("gunner", (5, 5))
    world.enemies.append(gunner)

    for _ in range(600):
        world.update(1 / 60, [])
        if not world.is_brick(4, 5):
            break

    assert not world.is_brick(4, 5)
