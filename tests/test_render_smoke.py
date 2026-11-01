from __future__ import annotations

import pygame
import pytest

import config
from game import boss as boss_module
from game import render
from game.upgrades import UPGRADE_POOL
from game.world import World


WIDTH = config.SCREEN_WIDTH
HEIGHT = config.SCREEN_HEIGHT


@pytest.fixture
def screen() -> pygame.Surface:
    return pygame.Surface((WIDTH, HEIGHT))


@pytest.fixture
def world() -> World:
    return World(0, seed=1)


def sampled_colors(surface: pygame.Surface, rect: pygame.Rect, step: int = 4):
    colors = set()
    for y in range(rect.top, rect.bottom, step):
        for x in range(rect.left, rect.right, step):
            colors.add(tuple(surface.get_at((x, y)))[:3])
    return colors


def changed_pixels(surface: pygame.Surface, color, step: int = 4) -> int:
    target = tuple(color)[:3]
    changed = 0
    for y in range(0, HEIGHT, step):
        for x in range(0, WIDTH, step):
            if tuple(surface.get_at((x, y)))[:3] != target:
                changed += 1
    return changed


def count_pixels_in_rect(
    surface: pygame.Surface,
    rect: pygame.Rect,
    predicate,
    step: int = 1,
    exclude: pygame.Rect | None = None,
) -> int:
    rect = rect.clip(surface.get_rect())
    count = 0
    for y in range(rect.top, rect.bottom, step):
        for x in range(rect.left, rect.right, step):
            if exclude is not None and exclude.collidepoint(x, y):
                continue
            pixel = tuple(surface.get_at((x, y)))[:3]
            if predicate(pixel):
                count += 1
    return count


def count_color_in_rect(
    surface: pygame.Surface,
    rect: pygame.Rect,
    color,
    tolerance: int = 0,
    step: int = 1,
) -> int:
    target = tuple(color)[:3]

    def matches(pixel):
        return all(
            abs(pixel[index] - target[index]) <= tolerance
            for index in range(3)
        )

    return count_pixels_in_rect(surface, rect, matches, step)


def is_warning_pink(pixel) -> bool:
    r, g, b = pixel
    return (
        r > 200
        and g > 150
        and b > 150
        and r - g >= 10
        and r - b >= 10
        and abs(g - b) < 45
    )


def is_warning_warm(pixel) -> bool:
    r, g, b = pixel
    return r > 120 and r - g > 50 and r - b > 40


def is_warning_orange(pixel) -> bool:
    r, g, b = pixel
    return r > 220 and 120 < g < 215 and b < 145


def is_shield_cyan(pixel) -> bool:
    r, g, b = pixel
    return g > 170 and b > 180 and g - r > 30


def is_laser_bright(pixel) -> bool:
    r, g, b = pixel
    return r > 160 and g > 190 and b > 210


def is_faded_text(pixel) -> bool:
    r, g, b = pixel
    return r > 80 and g > 90 and b > 100


def test_draw_world_changes_pixels(screen, world):
    screen.fill(config.BG)
    renderer = render.Renderer(screen)

    renderer.draw_world(world)

    assert changed_pixels(screen, config.BG) > 100


def test_draw_world_fills_hud(screen, world):
    screen.fill((255, 0, 255))
    renderer = render.Renderer(screen)

    renderer.draw_world(world)

    assert changed_pixels(screen, (255, 0, 255)) > 100
    hud = config.HUD_RECT
    assert len(sampled_colors(screen, hud, 3)) >= 3


def test_title_and_upgrade_have_distinct_colors(screen):
    renderer = render.Renderer(screen)

    screen.fill(config.BG)
    renderer.draw_title(0.4)
    assert len(sampled_colors(screen, screen.get_rect(), 8)) >= 3

    screen.fill(config.BG)
    offers = [list(UPGRADE_POOL[:3]), list(UPGRADE_POOL[3:6])]
    levels = [{}, {}]
    renderer.draw_upgrade(offers, levels, 0)
    assert len(sampled_colors(screen, screen.get_rect(), 8)) >= 3


def test_all_overlays_render(screen, world):
    renderer = render.Renderer(screen)

    for draw in (
        lambda: renderer.draw_controls(),
        lambda: renderer.draw_pause(),
        lambda: renderer.draw_intro(0, 1.0),
        lambda: renderer.draw_intro(config.BOSS_LEVEL, 0.4),
        lambda: renderer.draw_game_over(world, "The base was destroyed."),
        lambda: renderer.draw_victory(world),
    ):
        screen.fill(config.BG)
        draw()
        assert changed_pixels(screen, config.BG, step=8) > 20


def test_draw_intro_fades_text_with_remaining(screen):
    renderer = render.Renderer(screen)
    title_rect = pygame.Rect(400, 260, 480, 60)

    screen.fill(config.BG)
    renderer.draw_intro(0, 1.2)
    assert count_pixels_in_rect(screen, title_rect, is_faded_text) > 50

    screen.fill(config.BG)
    renderer.draw_intro(0, 0.0)
    assert count_pixels_in_rect(screen, title_rect, is_faded_text) == 0


def test_draw_world_draws_boss_telegraphs(screen):
    world = World(config.BOSS_LEVEL, seed=1)
    boss = world.boss
    assert boss is not None
    boss.telegraph = 0.5
    boss.telegraph_kind = "laser"
    boss.telegraph_direction = config.Direction.DOWN
    renderer = render.Renderer(screen)

    renderer.draw_world(world)
    beam_rect = pygame.Rect(636, 160, 8, 260)
    assert count_pixels_in_rect(screen, beam_rect, is_warning_pink) > 50

    boss.telegraph_kind = "aimed"
    boss.telegraph_target = pygame.Vector2(560, 180)
    renderer.draw_world(world)
    target_rect = pygame.Rect(536, 156, 48, 48)
    assert (
        count_pixels_in_rect(screen, target_rect, is_warning_warm) > 30
    )

    boss.telegraph_kind = "radial"
    renderer.draw_world(world)
    center_x, center_y = int(boss.center.x), int(boss.center.y)
    ring_region = pygame.Rect(center_x - 72, center_y - 72, 144, 144)
    inner_region = pygame.Rect(center_x - 35, center_y - 35, 70, 70)
    assert (
        count_pixels_in_rect(
            screen,
            ring_region,
            is_warning_orange,
            exclude=inner_region,
        )
        > 50
    )


def test_boss_upward_laser_telegraph_points_up(screen):
    world = World(config.BOSS_LEVEL, seed=1)
    boss = world.boss
    assert boss is not None
    boss.pos = pygame.Vector2(640, 300)
    boss.telegraph = 1.0
    boss.telegraph_kind = "laser"
    boss.telegraph_direction = config.Direction.UP
    renderer = render.Renderer(screen)

    renderer.draw_world(world)

    above_boss = pygame.Rect(636, 80, 8, 140)
    assert count_pixels_in_rect(screen, above_boss, is_warning_pink) > 30


def test_boss_laser_execute_preserves_up_direction():
    world = World(config.BOSS_LEVEL, seed=1)
    boss = world.boss
    assert boss is not None
    attack = boss_module._PendingAttack(
        "laser", 0.0, direction=config.Direction.UP
    )

    boss._execute(attack, world)

    assert world.lasers[-1].direction == config.Direction.UP


def test_draw_world_handles_eliminated_players_and_dead_base(screen):
    world = World(0, seed=1)
    world.players[0].alive = False
    world.players[0].eliminated = True
    world.players[0].respawn_timer = 0.0
    world.players[1].alive = False
    world.players[1].eliminated = False
    world.players[1].respawn_timer = 1.5
    world.base.alive = False
    world.base.hp = 0
    renderer = render.Renderer(screen)

    renderer.draw_world(world)

    assert changed_pixels(screen, config.BG) > 100
    cards = renderer._hud_rects()
    p1_status = pygame.Rect(
        cards[0].right - 115, cards[0].top + 4, 110, 20
    )
    p2_status = pygame.Rect(
        cards[1].right - 115, cards[1].top + 4, 110, 20
    )
    eliminated_color = (220, 110, 110)
    assert (
        count_color_in_rect(
            screen, p1_status, eliminated_color, tolerance=2
        )
        > 20
    )
    assert (
        count_color_in_rect(
            screen, p2_status, config.P2_AMBER, tolerance=2
        )
        > 20
    )
    destroyed_x_color = (226, 72, 72)
    assert (
        count_color_in_rect(
            screen, world.base.rect, destroyed_x_color, tolerance=4
        )
        > 20
    )


def test_enemy_counter_uses_boss_label_only_while_alive(screen):
    world = World(config.BOSS_LEVEL, seed=1)
    assert world.boss is not None
    renderer = render.Renderer(screen)
    counter = renderer._hud_rects()[5]
    boss_magenta = (224, 96, 224)

    renderer.draw_world(world)
    assert (
        count_color_in_rect(
            screen, counter, boss_magenta, tolerance=4
        )
        > 5
    )

    world.boss.alive = False
    renderer.draw_world(world)
    assert (
        count_color_in_rect(
            screen, counter, boss_magenta, tolerance=4
        )
        == 0
    )


def test_wall_cache_updates_when_bricks_are_destroyed(screen):
    world = World(0, seed=1)
    renderer = render.Renderer(screen)
    brick = None
    for ty, row in enumerate(world.grid):
        for tx, tile in enumerate(row):
            if tile == config.Tile.BRICK:
                brick = (tx, ty)
                break
        if brick is not None:
            break
    assert brick is not None

    renderer.draw_world(world)
    probe = (
        config.PLAYFIELD_X + brick[0] * config.TILE + config.TILE // 2,
        config.PLAYFIELD_Y + brick[1] * config.TILE + config.TILE // 2,
    )
    before = tuple(screen.get_at(probe))[:3]

    world.destroy_brick(*brick)
    renderer.draw_world(world)
    after = tuple(screen.get_at(probe))[:3]

    assert after != before


def test_draw_world_handles_skills_and_enemies(screen):
    world = World(0, seed=1)
    world.throw_grenade(world.players[1])
    world.fire_laser(world.players[0])
    world.spawn_enemy("tracker", (3, 2))
    world.spawn_enemy("elite", (20, 2))
    demolisher = world.spawn_enemy("demolisher", (11, 2))
    assert demolisher is not None
    demolisher.telegraph = 0.3
    elite = next(enemy for enemy in world.enemies if enemy.kind == "elite")
    grenade = world.grenades[-1]
    laser = world.lasers[-1]
    world.effects.shake_amount = 0.0
    renderer = render.Renderer(screen)

    renderer.draw_world(world)

    target = grenade.target
    reticle_rect = pygame.Rect(
        int(target.x) - 26, int(target.y) - 26, 52, 52
    )
    reticle_color = (229, 162, 54)
    assert (
        count_color_in_rect(
            screen, reticle_rect, reticle_color, tolerance=4
        )
        > 20
    )

    arc_t = 0.75
    arc_x = grenade.start.x + (target.x - grenade.start.x) * arc_t
    arc_y = grenade.start.y + (target.y - grenade.start.y) * arc_t
    arc_y -= (
        4.0
        * config.GRENADE_ARC_HEIGHT
        * arc_t
        * (1.0 - arc_t)
    )
    arc_rect = pygame.Rect(int(arc_x) - 5, int(arc_y) - 5, 11, 11)
    arc_color = render._scale(config.P2_AMBER, 0.7)
    assert (
        count_color_in_rect(screen, arc_rect, arc_color, tolerance=6)
        >= 5
    )

    ring_radius = int(config.DEMOLISHER_BLAST_RADIUS)
    demolisher_center = (
        int(demolisher.pos.x),
        int(demolisher.pos.y),
    )
    ring_region = pygame.Rect(
        demolisher_center[0] - ring_radius - 12,
        demolisher_center[1] - ring_radius - 12,
        ring_radius * 2 + 24,
        ring_radius * 2 + 24,
    )
    ring_inner = pygame.Rect(
        demolisher_center[0] - 40,
        demolisher_center[1] - 40,
        80,
        80,
    )
    assert (
        count_pixels_in_rect(
            screen,
            ring_region,
            is_warning_orange,
            exclude=ring_inner,
        )
        > 50
    )

    midpoint = laser.origin.lerp(laser.end, 0.5)
    beam_rect = pygame.Rect(
        int(midpoint.x) - 6, int(midpoint.y) - 20, 12, 40
    )
    assert count_pixels_in_rect(screen, beam_rect, is_laser_bright) > 20

    elite_center = (int(elite.pos.x), int(elite.pos.y))
    shield_band = pygame.Rect(
        elite_center[0] - 30, elite_center[1] - 14, 60, 28
    )
    assert count_pixels_in_rect(screen, shield_band, is_shield_cyan) > 20
