from __future__ import annotations

import random

import pygame

import config
from game import i18n
from game.audio import Audio
from game.difficulty import PROFILES
from game.input import choice_from_event, read_player_inputs
from game.render import Renderer
from game.run import RunState
from game.upgrades import Upgrade, roll_upgrades
from game.world import World

INTRO_DURATION = 1.2
MAX_DT = 0.05


class Game:
    def __init__(
        self,
        screen: pygame.Surface,
        seed: int | None = None,
        audio: Audio | None = None,
        difficulty: str = "normal",
        language: str = "zh",
    ) -> None:
        self.screen = screen
        self.seed = seed
        self.difficulty = difficulty
        self.language = (
            language if language in i18n.LANGUAGES else i18n.DEFAULT_LANGUAGE
        )
        self._run_seed = (
            int(seed) if seed is not None else random.randrange(1 << 31)
        )
        self.canvas = pygame.Surface(
            (config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
        )
        self.renderer = Renderer(self.canvas)
        self.renderer.set_language(self.language)
        self.audio = audio if audio is not None else Audio()
        self.state = "title"
        self.running = True
        self.level_index = 0
        self.world = self._make_world(
            0, self._fresh_stats(), self._fresh_levels()
        )
        self.intro_timer = 0.0
        self.offers: list[list[Upgrade]] = [[], []]
        self.chooser = 0
        self._chooser_queue: list[int] = []
        self.reason = ""
        self._time = 0.0
        self._skill_pressed: set[int] = set()
        self._clock = pygame.time.Clock()

    def _fresh_stats(self) -> list[config.PlayerStats]:
        return [config.PlayerStats() for _ in config.PLAYER_SPAWNS]

    def _fresh_levels(self) -> list[dict[str, int]]:
        return [{} for _ in config.PLAYER_SPAWNS]

    def _world_seed(self, level_index: int) -> int:
        return self._run_seed + level_index

    def _make_world(
        self,
        level_index: int,
        stats: list[config.PlayerStats],
        levels: list[dict[str, int]],
        *,
        difficulty: str | None = None,
    ) -> World:
        return World(
            level_index,
            seed=self._world_seed(level_index),
            player_stats=stats,
            upgrade_levels=levels,
            difficulty=self.difficulty if difficulty is None else difficulty,
        )

    def _capture_run_state(self) -> RunState:
        world = self.world
        return RunState(
            run_seed=self._run_seed,
            difficulty=self.difficulty,
            language=self.language,
            level_index=world.level_index,
            player_stats=[player.stats for player in world.players],
            upgrade_levels=[
                dict(levels) for levels in world.upgrade_levels
            ],
        )

    def _retry_level(self) -> None:
        state = self._capture_run_state()
        self.level_index = state.level_index
        self.world = self._make_world(
            state.level_index,
            state.player_stats,
            state.upgrade_levels,
            difficulty=state.difficulty,
        )
        self.state = "playing"
        self.intro_timer = INTRO_DURATION
        self.offers = [[], []]
        self.chooser = 0
        self._chooser_queue = []
        self.reason = ""
        self._skill_pressed.clear()

    def _new_run(self) -> None:
        self._run_seed = (
            int(self.seed)
            if self.seed is not None
            else random.randrange(1 << 31)
        )
        self.level_index = 0
        self.world = self._make_world(
            0, self._fresh_stats(), self._fresh_levels()
        )
        self.intro_timer = INTRO_DURATION
        self.offers = [[], []]
        self.chooser = 0
        self._chooser_queue = []
        self.reason = ""
        self._skill_pressed.clear()

    def _start_new_run(self) -> None:
        self._new_run()
        self.state = "playing"

    def _advance_level(self) -> None:
        next_index = self.world.level_index + 1
        if next_index >= config.LEVEL_COUNT:
            self.state = "victory"
            self.audio.play("win")
            return

        stats = [player.stats for player in self.world.players]
        levels = [
            dict(levels) for levels in self.world.upgrade_levels
        ]

        self.level_index = next_index
        self.world = self._make_world(next_index, stats, levels)
        self.state = "playing"
        self.intro_timer = INTRO_DURATION
        self.offers = [[], []]
        self.chooser = 0
        self._chooser_queue = []
        self._skill_pressed.clear()

    def _enter_upgrade(self) -> None:
        self.state = "upgrade"
        self.offers = [[], []]
        queue: list[int] = []
        for player in self.world.players:
            player_id = player.player_id
            rng = random.Random(
                self._run_seed + self.world.level_index * 2 + player_id
            )
            role = "p1" if player_id == 0 else "p2"
            self.offers[player_id] = roll_upgrades(
                rng, self.world.upgrade_levels[player_id], 3, role=role
            )
            queue.append(player_id)

        self._chooser_queue = queue
        if queue:
            self.chooser = queue[0]
            self._skill_pressed.clear()
            return

        self.chooser = 0
        self._advance_level()

    def _choose_upgrade(self, event: pygame.event.Event) -> None:
        if not 0 <= self.chooser < len(self.offers):
            return
        current = self.offers[self.chooser]
        index = choice_from_event(event, len(current))
        if index is None or index >= len(current):
            return

        upgrade = current[index]
        if self.world.apply_upgrade(self.chooser, upgrade.id):
            self.audio.play("pick")

        if self.chooser in self._chooser_queue:
            self._chooser_queue.remove(self.chooser)
        if self._chooser_queue:
            self.chooser = self._chooser_queue[0]
        else:
            self._advance_level()

    def _loss_reason(self) -> str:
        return "gameover.base_destroyed"

    def _toggle_language(self) -> None:
        keys = list(i18n.LANGUAGES)
        index = keys.index(self.language) if self.language in keys else 0
        self.language = keys[(index + 1) % len(keys)]
        self.renderer.set_language(self.language)

    def _change_difficulty(self, step: int) -> None:
        keys = list(PROFILES)
        index = keys.index(self.difficulty) if self.difficulty in keys else 0
        self.difficulty = keys[(index + step) % len(keys)]

    def _sync_status(self) -> None:
        status = self.world.status
        if status == "cleared":
            self._enter_upgrade()
        elif status == "lost":
            self.state = "gameover"
            self.reason = self._loss_reason()
            self.audio.play("lose")
        elif status == "victory":
            self.state = "victory"
            self.audio.play("win")

    def _register_skill(self, key: int) -> None:
        for player_id, mapping in enumerate(config.KEYMAP):
            if key == mapping["skill"]:
                self._skill_pressed.add(player_id)

    def _process_playing(self, dt: float) -> None:
        world = self.world
        inputs = read_player_inputs(
            pygame.key.get_pressed(), self._skill_pressed
        )

        for player_id, player_input in enumerate(inputs):
            if player_id >= len(world.players):
                break
            player = world.players[player_id]
            if player_input.shoot and player.can_shoot():
                self.audio.play("shoot")
            if not player_input.skill:
                continue
            if player_id == 0:
                if world.throw_grenade(player):
                    self.audio.play("explosion")
            elif world.fire_laser(player):
                self.audio.play("laser")

        self._skill_pressed.clear()
        world.update(dt, inputs)
        for _ in world.pickup_events:
            self.audio.play("pick")
        world.pickup_events.clear()
        if self.intro_timer > 0.0:
            self.intro_timer = max(0.0, self.intro_timer - dt)
        self._sync_status()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type != pygame.KEYDOWN:
            return

        key = event.key
        if key == pygame.K_l and self.state in (
            "title",
            "controls",
            "paused",
        ):
            self._toggle_language()
            return
        if key == config.PAUSE_KEY:
            if self.state == "playing":
                self.state = "paused"
                self._skill_pressed.clear()
            elif self.state == "paused":
                self.state = "playing"
            elif self.state in ("controls", "gameover", "victory"):
                self.state = "title"
                self._skill_pressed.clear()
            return

        if self.state == "title":
            if key == config.CONFIRM_KEY:
                self.state = "controls"
            elif key == pygame.K_LEFT:
                self._change_difficulty(-1)
            elif key == pygame.K_RIGHT:
                self._change_difficulty(1)
        elif self.state == "controls":
            if key == config.CONFIRM_KEY:
                self._start_new_run()
        elif self.state == "playing":
            self._register_skill(key)
        elif self.state == "upgrade":
            self._choose_upgrade(event)
        elif self.state == "gameover":
            if key == config.CONFIRM_KEY:
                self._retry_level()
        elif self.state == "victory":
            if key == config.CONFIRM_KEY:
                self._start_new_run()

    def update(self, dt: float) -> None:
        try:
            dt = float(dt)
        except (TypeError, ValueError):
            dt = 0.0
        dt = max(0.0, min(dt, MAX_DT))

        if self.state in ("title", "controls"):
            self._time += dt
            return
        if self.state != "playing":
            return

        self._time += dt
        self._process_playing(dt)

    def draw(self) -> None:
        if self.state == "title":
            self.renderer.draw_title(self._time, self.difficulty)
        elif self.state == "controls":
            self.renderer.draw_controls()
        elif self.state == "playing":
            self.renderer.draw_world(self.world)
            if self.intro_timer > 0.0:
                self.renderer.draw_intro(
                    self.level_index, self.intro_timer
                )
        elif self.state == "paused":
            self.renderer.draw_world(self.world)
            self.renderer.draw_pause(self.world)
        elif self.state == "upgrade":
            self.renderer.draw_world(self.world)
            self.renderer.draw_upgrade(
                self.offers, self.world.upgrade_levels, self.chooser
            )
        elif self.state == "gameover":
            self.renderer.draw_world(self.world)
            self.renderer.draw_game_over(self.world, self.reason)
        elif self.state == "victory":
            self.renderer.draw_world(self.world)
            self.renderer.draw_victory(self.world)

        self._present()

    def _present(self) -> None:
        target = self.screen.get_rect()
        if self.screen.get_size() == self.canvas.get_size():
            self.screen.blit(self.canvas, (0, 0))
            return

        scale = min(
            target.width / config.SCREEN_WIDTH,
            target.height / config.SCREEN_HEIGHT,
        )
        width = max(1, int(config.SCREEN_WIDTH * scale))
        height = max(1, int(config.SCREEN_HEIGHT * scale))
        scaled = pygame.transform.smoothscale(
            self.canvas, (width, height)
        )
        self.screen.fill((0, 0, 0))
        self.screen.blit(
            scaled, scaled.get_rect(center=target.center)
        )

    def run(self) -> None:
        self._clock = pygame.time.Clock()
        while self.running:
            dt = self._clock.tick(config.FPS) / 1000.0
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt)
            self.draw()
            pygame.display.flip()
