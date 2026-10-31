import pygame

import config
from game import input as game_input


class FakeKeys:
    def __init__(self, *pressed):
        self.pressed = set(pressed)

    def __getitem__(self, key):
        return key in self.pressed


def test_wasd_maps_to_player_one_and_arrows_to_player_two():
    expectations = (
        ("up", config.Direction.UP),
        ("down", config.Direction.DOWN),
        ("left", config.Direction.LEFT),
        ("right", config.Direction.RIGHT),
    )

    for action, direction in expectations:
        p1_key = config.KEYMAP[0][action]
        p2_key = config.KEYMAP[1][action]

        inputs = game_input.read_player_inputs(FakeKeys(p1_key))
        assert inputs[0].move == direction
        assert inputs[1].move is None

        inputs = game_input.read_player_inputs(FakeKeys(p2_key))
        assert inputs[1].move == direction
        assert inputs[0].move is None


def test_opposing_vertical_keys_do_not_produce_diagonal_movement():
    p1_keys = FakeKeys(config.KEYMAP[0]["up"], config.KEYMAP[0]["down"])
    p2_keys = FakeKeys(config.KEYMAP[1]["up"], config.KEYMAP[1]["down"])

    p1_inputs = game_input.read_player_inputs(p1_keys)
    p2_inputs = game_input.read_player_inputs(p2_keys)

    assert p1_inputs[0].move is None
    assert p2_inputs[1].move is None


def test_mixed_axes_resolve_to_single_direction():
    keys = FakeKeys(config.KEYMAP[0]["up"], config.KEYMAP[0]["right"])

    inputs = game_input.read_player_inputs(keys)

    assert inputs[0].move in (
        config.Direction.UP,
        config.Direction.RIGHT,
    )


def test_shoot_keys_are_mapped_per_player():
    p1_inputs = game_input.read_player_inputs(FakeKeys(config.KEYMAP[0]["shoot"]))
    assert p1_inputs[0].shoot is True
    assert p1_inputs[1].shoot is False

    p2_inputs = game_input.read_player_inputs(FakeKeys(config.KEYMAP[1]["shoot"]))
    assert p2_inputs[1].shoot is True
    assert p2_inputs[0].shoot is False


def test_skill_requires_key_press_and_matching_held_player_id():
    p1_skill = config.KEYMAP[0]["skill"]
    p2_skill = config.KEYMAP[1]["skill"]

    p1_inputs = game_input.read_player_inputs(
        FakeKeys(p1_skill), skill_pressed={0}
    )
    assert p1_inputs[0].skill is True
    assert p1_inputs[1].skill is False

    p2_inputs = game_input.read_player_inputs(
        FakeKeys(p2_skill), skill_pressed={1}
    )
    assert p2_inputs[1].skill is True
    assert p2_inputs[0].skill is False

    wrong_owner = game_input.read_player_inputs(
        FakeKeys(p1_skill), skill_pressed={1}
    )
    assert wrong_owner[0].skill is False

    no_skill_held = game_input.read_player_inputs(
        FakeKeys(), skill_pressed={0, 1}
    )
    assert no_skill_held[0].skill is False
    assert no_skill_held[1].skill is False


def test_skill_defaults_to_not_pressed_without_held_set():
    p1_inputs = game_input.read_player_inputs(
        FakeKeys(config.KEYMAP[0]["skill"])
    )
    p2_inputs = game_input.read_player_inputs(
        FakeKeys(config.KEYMAP[1]["skill"])
    )

    assert p1_inputs[0].skill is False
    assert p2_inputs[1].skill is False


def test_read_player_inputs_returns_one_input_per_player():
    inputs = game_input.read_player_inputs(FakeKeys())

    assert len(inputs) == len(config.KEYMAP) == 2
    assert inputs[0] is not inputs[1]


def test_choice_keys_map_to_zero_based_choices():
    for index, key in enumerate(config.CHOICE_KEYS):
        event = pygame.event.Event(pygame.KEYDOWN, key=key)
        assert game_input.choice_from_event(event) == index


def test_choice_from_event_ignores_non_keydown_and_unknown_keys():
    assert (
        game_input.choice_from_event(
            pygame.event.Event(pygame.KEYUP, key=config.CHOICE_KEYS[0])
        )
        is None
    )
    assert (
        game_input.choice_from_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_q)
        )
        is None
    )


def test_choice_from_event_respects_count_limit():
    third_choice = pygame.event.Event(pygame.KEYDOWN, key=config.CHOICE_KEYS[2])

    assert game_input.choice_from_event(third_choice, count=2) is None
    assert game_input.choice_from_event(third_choice, count=3) == 2
