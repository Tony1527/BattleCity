from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import pygame

from config import CHOICE_KEYS, Direction, KEYMAP


@dataclass
class PlayerInput:
    move: Direction | None = None
    shoot: bool = False
    skill: bool = False


def _pressed(keys: Mapping[int, bool], key: int) -> bool:
    try:
        return bool(keys[key])
    except (KeyError, IndexError):
        return False


def _read_move(keys: Mapping[int, bool], mapping: dict[str, int]) -> Direction | None:
    dx = int(_pressed(keys, mapping["right"])) - int(_pressed(keys, mapping["left"]))
    dy = int(_pressed(keys, mapping["down"])) - int(_pressed(keys, mapping["up"]))
    if dx == 0 and dy == 0:
        return None
    return Direction.from_vector(dx, dy)


def read_player_inputs(
    keys: Mapping[int, bool], skill_pressed: set[int] | None = None
) -> list[PlayerInput]:
    held_skills = set() if skill_pressed is None else skill_pressed
    inputs: list[PlayerInput] = []

    for player_id, mapping in enumerate(KEYMAP):
        inputs.append(
            PlayerInput(
                move=_read_move(keys, mapping),
                shoot=_pressed(keys, mapping["shoot"]),
                skill=(
                    player_id in held_skills
                    and _pressed(keys, mapping["skill"])
                ),
            )
        )

    return inputs


def choice_from_event(event: pygame.event.Event, count: int = 3) -> int | None:
    if event.type != pygame.KEYDOWN:
        return None

    for index, key in enumerate(CHOICE_KEYS[: max(0, count)]):
        if event.key == key:
            return index
    return None
