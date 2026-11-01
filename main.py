from __future__ import annotations

import argparse
import sys

import pygame

import config
from game.states import Game


def _positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Battle City - Holographic Armory"
    )
    parser.add_argument(
        "--seed", type=int, default=None, help="deterministic run seed"
    )
    parser.add_argument(
        "--width",
        type=_positive_int,
        default=config.SCREEN_WIDTH,
        help="window width in pixels",
    )
    parser.add_argument(
        "--height",
        type=_positive_int,
        default=config.SCREEN_HEIGHT,
        help="window height in pixels",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        pygame.mixer.pre_init(44100, -16, 2, 512)
    except pygame.error:
        pass

    try:
        pygame.init()
    except pygame.error:
        pass

    try:
        screen = pygame.display.set_mode((args.width, args.height))
    except pygame.error as error:
        print(f"Unable to create window: {error}", file=sys.stderr)
        pygame.quit()
        return 1

    pygame.display.set_caption("Battle City - Holographic Armory")

    try:
        game = Game(screen, seed=args.seed)
        game.run()
    finally:
        pygame.quit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
