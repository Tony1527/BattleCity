from __future__ import annotations

import pygame
import pytest

import config
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


def test_draw_world_handles_boss_and_telegraph(screen):
    world = World(config.BOSS_LEVEL, seed=1)
    boss = world.boss
    assert boss is not None
    boss.telegraph = 0.5
    boss.telegraph_kind = "laser"
    boss.telegraph_direction = config.Direction.DOWN
    boss.telegraph_target = pygame.Vector2(boss.center.x, boss.center.y + 200)
    renderer = render.Renderer(screen)

    renderer.draw_world(world)

    assert changed_pixels(screen, config.BG) > 100

    boss.telegraph_kind = "radial"
    renderer.draw_world(world)
    boss.telegraph_kind = "aimed"
    renderer.draw_world(world)


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


def test_draw_world_handles_skills_and_enemies(screen, world):
    player = world.players[0]
    world.throw_grenade(player)
    world.fire_laser(player)
    world.spawn_enemy("tracker", (3, 2))
    world.spawn_enemy("elite", (20, 2))
    demolisher = world.spawn_enemy("demolisher", (11, 2))
    assert demolisher is not None
    demolisher.telegraph = 0.3
    world.base.shield = 2
    world.base.hp = 2
    world.players[0].hp = 2
    world.players[1].alive = False
    world.players[1].respawn_timer = 1.5
    renderer = render.Renderer(screen)

    renderer.draw_world(world)

    assert changed_pixels(screen, config.BG) > 100
