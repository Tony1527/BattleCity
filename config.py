from __future__ import annotations

from dataclasses import dataclass, replace
from enum import IntEnum

import pygame

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60

TILE = 48
GRID_COLS = 24
GRID_ROWS = 13
PLAYFIELD_X = 64
PLAYFIELD_Y = 0
PLAYFIELD_WIDTH = GRID_COLS * TILE
PLAYFIELD_HEIGHT = GRID_ROWS * TILE
HUD_Y = 624
HUD_HEIGHT = SCREEN_HEIGHT - HUD_Y
PLAYFIELD_RECT = pygame.Rect(
    PLAYFIELD_X, PLAYFIELD_Y, PLAYFIELD_WIDTH, PLAYFIELD_HEIGHT
)
HUD_RECT = pygame.Rect(0, HUD_Y, SCREEN_WIDTH, HUD_HEIGHT)

BG = (10, 14, 22)
FLOOR = (18, 24, 34)
GRID = (30, 42, 58)
STEEL = (86, 102, 122)
BRICK = (150, 84, 64)
P1_BLUE = (70, 170, 255)
P2_AMBER = (255, 180, 60)
ENEMY_RED = (230, 70, 70)
ENEMY_ORANGE = (255, 140, 60)
HOLO_WHITE = (210, 240, 255)

_VECTORS = ((0, -1), (1, 0), (0, 1), (-1, 0))


class Direction(IntEnum):
    UP = 0
    RIGHT = 1
    DOWN = 2
    LEFT = 3

    @property
    def vector(self) -> tuple[int, int]:
        return _VECTORS[self.value]

    @property
    def angle(self) -> float:
        return float(self.value * 90)

    @classmethod
    def from_vector(cls, dx: float, dy: float) -> Direction:
        if dx == 0 and dy == 0:
            raise ValueError("a zero vector has no direction")
        if abs(dx) >= abs(dy):
            return cls.RIGHT if dx > 0 else cls.LEFT
        return cls.DOWN if dy > 0 else cls.UP


class Tile(IntEnum):
    EMPTY = 0
    BRICK = 1
    STEEL = 2


@dataclass
class PlayerStats:
    max_hp: int = 3
    speed: float = 150.0
    fire_interval: float = 0.35
    bullet_damage: int = 1
    bullet_speed: float = 400.0
    damage_reduction: float = 0.0
    grenade_cooldown: float = 6.0
    grenade_damage: int = 40
    grenade_radius: float = 1.5 * TILE
    laser_cooldown: float = 5.0
    laser_damage: int = 60
    laser_range: float = 8 * TILE
    extra_lives: int = 0
    base_shield: int = 0
    grenade_split: int = 0
    laser_reflect: int = 0

    def clone(self) -> PlayerStats:
        return replace(self)


@dataclass(frozen=True)
class EnemySpec:
    kind: str
    hp: int
    speed: float
    fire_interval: float
    bullet_speed: float
    bullet_damage: int
    attack_range: float
    score: int


ENEMY_SPECS = {
    "tracker": EnemySpec("tracker", 2, 78, 1.5, 230, 1, 5 * TILE, 10),
    "gunner": EnemySpec("gunner", 3, 60, 1.9, 300, 1, 8 * TILE, 15),
    "demolisher": EnemySpec("demolisher", 4, 95, 2.5, 0, 0, 1.5 * TILE, 20),
}

PLAYER_SIZE = 36
ENEMY_SIZE = 36
BULLET_SIZE = 8
PLAYER_SPEED = 150.0
PLAYER_HP = 3
PLAYER_FIRE_INTERVAL = 0.35
PLAYER_BULLET_SPEED = 400.0
PLAYER_BULLET_DAMAGE = 1
HIT_INVULN = 0.5
RESPAWN_DELAY = 3.0
RESPAWN_INVULN = 2.0
SHARED_LIVES = 3

BASE_HP = 3
BASE_TILES = ((11, 11), (12, 11), (11, 12), (12, 12))
BASE_ENTRANCES = ((11, 10), (12, 10), (10, 11), (13, 11))

ENEMY_SPAWNS = ((3, 2), (11, 2), (20, 2))
PLAYER_SPAWNS = ((8, 10), (15, 10))

ENEMY_QUOTA = (8, 10, 12, 14, 16, 18, 20, 0)
MAX_ACTIVE_ENEMIES = (3, 3, 4, 4, 5, 5, 6, 0)
SPAWN_INTERVAL = (6.0, 5.5, 5.0, 4.5, 4.0, 3.5, 3.0, 0.0)
SPAWN_START_DELAY = 0.5
ELITE_LEVELS = (3, 6)
BOSS_LEVEL = 7
LEVEL_COUNT = 8

GUNNER_PREFERRED_MIN = 4
GUNNER_PREFERRED_MAX = 6

ELITE_SHIELD = 12
ELITE_SHIELD_REGEN = 3.0
ELITE_SUMMON_INTERVAL = 9.0
ELITE_MAX_SUMMONS = 2
ELITE_SPREAD_SHOTS = 3
DEMOLISHER_TELEGRAPH = 0.6
DEMOLISHER_BLAST_RADIUS = 1.5 * TILE
DEMOLISHER_BLAST_DAMAGE = 2

BOSS_HP = 360
BOSS_SPEED = 32
BOSS_SIZE = 96
BOSS_PHASE_THRESHOLDS = (0.66, 0.33)
BOSS_DRIFT_RANGE = 4 * TILE
BOSS_DRIFT_MARGIN = 16

BOSS_AIM_INTERVAL = (1.2, 1.2, 0.8)
BOSS_RADIAL_INTERVAL = (3.5, 3.5, 2.4)
BOSS_LASER_INTERVAL = (6.0, 6.0, 4.5)
BOSS_RADIAL_COUNT = (8, 12, 16)
BOSS_AIM_BASE_EVERY = 2
BOSS_LASER_BASE_EVERY = 2

BOSS_AIM_TELEGRAPH = 0.35
BOSS_RADIAL_TELEGRAPH = 0.5
BOSS_LASER_TELEGRAPH = 1.0
BOSS_PHASE_FLASH = 0.6

BOSS_BULLET_SPEED = 260.0
BOSS_BULLET_DAMAGE = 1
BOSS_TRANSITION_SUMMONS = (0, 2, 3)
BOSS_MAX_SUMMONS_PER_TRANSITION = 3

GRENADE_COOLDOWN = 6.0
GRENADE_DAMAGE = 40
GRENADE_RADIUS = 1.5 * TILE
GRENADE_FRIENDLY_FACTOR = 0.35
GRENADE_FLIGHT = 0.6
GRENADE_RANGE = 5 * TILE
GRENADE_ARC_HEIGHT = 26.0
GRENADE_MARGIN = 8
GRENADE_SPLIT_OFFSET = 30.0

LASER_COOLDOWN = 5.0
LASER_DAMAGE = 60
LASER_RANGE = 8 * TILE
LASER_LIFE = 0.12
LASER_SAMPLE_STEP = 2
LASER_MAX_SAMPLES = 1024
LASER_HIT_TOLERANCE = 18.0

BRICK_CHANCE = 0.30
STEEL_CHANCE = 0.06
GENERATION_RETRIES = 60
CORRIDOR_BANDS = ((2, 5), (10, 13), (18, 21))
SPAWN_SAFE_RADIUS = 1
MIN_ROUTES = 3
MAX_ROUTE_OVERLAP = 0.30
MIN_BASE_ENTRANCE_DIRECTIONS = 2

KEYMAP = (
    {
        "up": pygame.K_w,
        "down": pygame.K_s,
        "left": pygame.K_a,
        "right": pygame.K_d,
        "shoot": pygame.K_SPACE,
        "skill": pygame.K_f,
    },
    {
        "up": pygame.K_UP,
        "down": pygame.K_DOWN,
        "left": pygame.K_LEFT,
        "right": pygame.K_RIGHT,
        "shoot": pygame.K_PERIOD,
        "skill": pygame.K_SLASH,
    },
)
PAUSE_KEY = pygame.K_ESCAPE
CONFIRM_KEY = pygame.K_RETURN
CHOICE_KEYS = (pygame.K_1, pygame.K_2, pygame.K_3)
