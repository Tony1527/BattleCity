import pygame

from game.geometry import in_bounds, point_to_tile, tile_center, tile_rect


def test_tile_rect_applies_playfield_offset():
    assert tile_rect(0, 0) == pygame.Rect(64, 0, 48, 48)
    assert tile_rect(23, 12) == pygame.Rect(64 + 23 * 48, 12 * 48, 48, 48)


def test_tile_center_returns_rect_center():
    assert tile_center(2, 3) == pygame.Vector2(64 + 2 * 48 + 24, 3 * 48 + 24)
    assert pygame.Vector2(tile_rect(2, 3).center) == tile_center(2, 3)


def test_point_to_tile_round_trips_tile_centers():
    for tx, ty in ((0, 0), (1, 1), (2, 3), (11, 10), (23, 12)):
        assert point_to_tile(tile_center(tx, ty)) == (tx, ty)


def test_point_to_tile_uses_floor_division():
    assert point_to_tile((64, 0)) == (0, 0)
    assert point_to_tile((64 + 47, 47)) == (0, 0)
    assert point_to_tile((64 + 48, 48)) == (1, 1)


def test_in_bounds_detects_edges_and_overflow():
    assert in_bounds(0, 0)
    assert in_bounds(23, 12)
    assert not in_bounds(-1, 0)
    assert not in_bounds(24, 0)
    assert not in_bounds(0, -1)
    assert not in_bounds(0, 13)
