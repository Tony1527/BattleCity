from __future__ import annotations

import pygame

from config import GRID_COLS, GRID_ROWS, PLAYFIELD_X, PLAYFIELD_Y, TILE


def tile_rect(tx: int, ty: int) -> pygame.Rect:
    return pygame.Rect(
        PLAYFIELD_X + tx * TILE,
        PLAYFIELD_Y + ty * TILE,
        TILE,
        TILE,
    )


def tile_center(tx: int, ty: int) -> pygame.Vector2:
    return pygame.Vector2(
        PLAYFIELD_X + tx * TILE + TILE / 2,
        PLAYFIELD_Y + ty * TILE + TILE / 2,
    )


def point_to_tile(pos: tuple[float, float] | pygame.Vector2) -> tuple[int, int]:
    return (
        int((pos[0] - PLAYFIELD_X) // TILE),
        int((pos[1] - PLAYFIELD_Y) // TILE),
    )


def in_bounds(tx: int, ty: int) -> bool:
    return 0 <= tx < GRID_COLS and 0 <= ty < GRID_ROWS
