from __future__ import annotations

import math
from pathlib import Path

import pygame

import config
from game import i18n
from game.upgrades import Upgrade

_FONT_SIZES = (
    ("font_xs", 18),
    ("font_s", 22),
    ("font_m", 30),
    ("font_l", 48),
    ("font_xl", 84),
)
_SYSTEM_CJK_FONTS = (
    "pingfangsc",
    "hiraginosansgb",
    "stheiti",
    "heiti sc",
    "microsoftyahei",
    "simhei",
    "notosanscjksc",
    "notosanssc",
    "arialunicodems",
)

_HUD_INNER_Y = 10
_HUD_CARD_HEIGHT = 76
_HUD_PANEL = (10, 16, 24)
_HUD_BORDER = (42, 78, 102)
_HUD_TEXT = (222, 238, 250)
_HUD_MUTED = (128, 156, 178)
_PANEL_FILL = (12, 20, 30)
_STEEL_DARK = (40, 50, 64)
_STEEL_HIGHLIGHT = (162, 184, 204)
_STEEL_SHADOW = (48, 58, 72)
_HOLO_EDGE = (160, 214, 245)
_ENEMY_DEMOLISHER = (242, 112, 58)
_ELITE_MAGENTA = (224, 96, 224)
_ELITE_LIGHT = (255, 176, 255)
_BOSS_PHASE_COLORS = {
    1: (232, 74, 74),
    2: (255, 146, 64),
    3: (226, 96, 255),
}
_REVIVE_DIAMOND = (208, 238, 250)


def _clamp_channel(value: float) -> int:
    return max(0, min(255, int(value)))


def _scale(color: tuple[int, ...], factor: float) -> tuple[int, int, int]:
    return tuple(_clamp_channel(channel * factor) for channel in color[:3])


class Renderer:
    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.width, self.height = screen.get_size()
        self.font_path: Path | None = None
        for attribute, size in _FONT_SIZES:
            font, loaded_path = self._load_font(size)
            setattr(self, attribute, font)
            if loaded_path is not None:
                self.font_path = loaded_path
        self.language = "en"

        self.hud_rect = pygame.Rect(
            0, self.height - config.HUD_HEIGHT, self.width, config.HUD_HEIGHT
        )
        self._glow = pygame.Surface((self.width, self.height))
        self._overlay = pygame.Surface(
            (self.width, self.height), pygame.SRCALPHA
        )
        self._tank_cache: dict[tuple, pygame.Surface] = {}
        self._background = pygame.Surface((self.width, self.height))
        self._build_background()
        self._brick_image = self._build_brick_image()
        self._steel_image = self._build_steel_image()
        self._steel_glow_image = self._build_steel_glow_image()
        self._wall_signature: tuple | None = None
        self._wall_surface: pygame.Surface | None = None
        self._wall_glow: pygame.Surface | None = None

    def _load_font(
        self, size: int
    ) -> tuple[pygame.font.Font, Path | None]:
        try:
            if config.FONT_PATH.exists():
                return (
                    pygame.font.Font(str(config.FONT_PATH), size),
                    config.FONT_PATH,
                )
        except (OSError, pygame.error):
            pass

        for name in _SYSTEM_CJK_FONTS:
            path = pygame.font.match_font(name)
            if not path:
                continue
            try:
                return pygame.font.Font(path, size), None
            except (OSError, pygame.error):
                continue
        return pygame.font.Font(None, size), None

    def set_language(self, language: str) -> None:
        self.language = (
            language if language in i18n.LANGUAGES else i18n.DEFAULT_LANGUAGE
        )

    def tr(self, key: str, **kwargs) -> str:
        return i18n.tr(self.language, key, **kwargs)

    # ------------------------------------------------------------------
    # Low level helpers
    # ------------------------------------------------------------------
    def _build_background(self) -> None:
        bg = self._background
        bg.fill(config.BG)
        playfield = config.PLAYFIELD_RECT.clip(bg.get_rect())
        pygame.draw.rect(bg, config.FLOOR, playfield)

        step = config.TILE
        for x in range(playfield.left, playfield.right + 1, step):
            pygame.draw.line(
                bg, config.GRID, (x, playfield.top), (x, playfield.bottom - 1)
            )
        for y in range(playfield.top, playfield.bottom + 1, step):
            pygame.draw.line(
                bg, config.GRID, (playfield.left, y), (playfield.right - 1, y)
            )

        for y in range(0, self.height, 3):
            pygame.draw.line(bg, (12, 17, 26), (0, y), (self.width, y))

        vignette = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        bands = 26
        for index in range(bands):
            falloff = 1.0 - index / bands
            alpha = int(66 * falloff * falloff)
            if alpha <= 0:
                continue
            inset = index * 5
            rect = pygame.Rect(
                inset,
                inset,
                self.width - inset * 2,
                self.height - inset * 2,
            )
            if rect.width <= 0 or rect.height <= 0:
                break
            pygame.draw.rect(vignette, (0, 0, 0, alpha), rect, width=10)
        bg.blit(vignette, (0, 0))

        pygame.draw.rect(bg, (46, 82, 108), playfield, width=2)
        corner = 22
        for x, y, dx, dy in (
            (playfield.left, playfield.top, 1, 1),
            (playfield.right, playfield.top, -1, 1),
            (playfield.left, playfield.bottom, 1, -1),
            (playfield.right, playfield.bottom, -1, -1),
        ):
            pygame.draw.line(
                bg,
                config.HOLO_WHITE,
                (x, y),
                (x + dx * corner, y),
                2,
            )
            pygame.draw.line(
                bg,
                config.HOLO_WHITE,
                (x, y),
                (x, y + dy * corner),
                2,
            )

    def _begin_glow(self) -> None:
        self._glow.fill((0, 0, 0))

    def _end_glow(self) -> None:
        self.screen.blit(
            self._glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD
        )

    def _glow_circle(
        self,
        color: tuple[int, ...],
        center: tuple[float, float],
        radius: float,
        layers: int = 3,
        strength: float = 1.0,
    ) -> None:
        if radius <= 0 or strength <= 0:
            return
        cx, cy = int(center[0]), int(center[1])
        for layer in range(layers, 0, -1):
            frac = layer / layers
            falloff = strength * (0.12 + 0.88 * (1.0 - frac))
            ring_color = _scale(color, falloff)
            pygame.draw.circle(
                self._glow, ring_color, (cx, cy), max(1, int(radius * frac))
            )

    def _glow_rect(
        self,
        color: tuple[int, ...],
        rect: pygame.Rect,
        strength: float = 0.4,
    ) -> None:
        if strength <= 0:
            return
        for index, factor in enumerate((0.18, 0.32, 0.5)):
            inset = index * 3
            glow_rect = rect.inflate(-inset * 2, -inset * 2)
            if glow_rect.width <= 0 or glow_rect.height <= 0:
                continue
            pygame.draw.rect(
                self._glow,
                _scale(color, strength * factor),
                glow_rect,
                width=3,
                border_radius=4,
            )

    def _glow_line(
        self,
        color: tuple[int, ...],
        start: tuple[int, int],
        end: tuple[int, int],
        width: float,
        strength: float = 1.0,
    ) -> None:
        if strength <= 0 or width <= 0:
            return
        for factor, scale in ((0.25, 2.4), (0.6, 1.0)):
            pygame.draw.line(
                self._glow,
                _scale(color, strength * factor),
                start,
                end,
                max(1, int(width * scale)),
            )

    def _text(
        self,
        text: str,
        font: pygame.font.Font,
        color: tuple[int, ...],
        pos: tuple[float, float],
        align: str = "left",
        shadow: bool = True,
        alpha: int = 255,
    ) -> pygame.Rect:
        image = font.render(str(text), True, color)
        rect = image.get_rect()
        if align == "center":
            rect.center = (int(pos[0]), int(pos[1]))
        elif align == "right":
            rect.topright = (int(pos[0]), int(pos[1]))
        else:
            rect.topleft = (int(pos[0]), int(pos[1]))
        alpha = max(0, min(255, int(alpha)))
        if alpha < 255:
            image.set_alpha(alpha)
        if shadow:
            shadow_image = font.render(str(text), True, (0, 0, 0))
            if alpha < 255:
                shadow_image.set_alpha(alpha)
            self.screen.blit(shadow_image, rect.move(1, 2))
        self.screen.blit(image, rect)
        return rect

    def _wrap_text(
        self, text: str, font: pygame.font.Font, max_width: int
    ) -> list[str]:
        lines: list[str] = []
        for paragraph in str(text).split("\n"):
            current = ""
            for word in paragraph.split():
                candidate = f"{current} {word}".strip()
                if font.size(candidate)[0] <= max_width:
                    current = candidate
                    continue
                if current:
                    lines.append(current)
                    current = ""
                if font.size(word)[0] <= max_width:
                    current = word
                    continue
                chunk = ""
                for character in word:
                    if font.size(chunk + character)[0] <= max_width:
                        chunk += character
                    else:
                        if chunk:
                            lines.append(chunk)
                        chunk = character
                current = chunk
            if current:
                lines.append(current)
        return lines

    def _panel(
        self,
        rect: pygame.Rect,
        fill: tuple[int, ...] = _PANEL_FILL,
        border: tuple[int, ...] = _HUD_BORDER,
        accent: tuple[int, ...] | None = None,
        radius: int = 6,
    ) -> None:
        pygame.draw.rect(self.screen, fill, rect, border_radius=radius)
        pygame.draw.rect(
            self.screen, border, rect, width=1, border_radius=radius
        )
        if accent is not None:
            pygame.draw.line(
                self.screen,
                accent,
                (rect.left + 10, rect.top),
                (rect.right - 10, rect.top),
                2,
            )

    def _dim(
        self, alpha: int = 170, color: tuple[int, int, int] = (3, 6, 12)
    ) -> None:
        self._overlay.fill((*color, max(0, min(255, int(alpha)))))
        self.screen.blit(self._overlay, (0, 0))

    def _dim_rect(
        self,
        rect: pygame.Rect,
        alpha: int,
        color: tuple[int, int, int] = (3, 6, 12),
    ) -> None:
        self._overlay.fill((0, 0, 0, 0))
        pygame.draw.rect(
            self._overlay,
            (*color, max(0, min(255, int(alpha)))),
            rect,
        )
        self.screen.blit(self._overlay, (0, 0))

    def _diamond(
        self,
        center: tuple[float, float],
        radius: float,
        color: tuple[int, ...],
        width: int = 0,
    ) -> None:
        cx, cy = int(center[0]), int(center[1])
        r = int(radius)
        points = [
            (cx, cy - r),
            (cx + r, cy),
            (cx, cy + r),
            (cx - r, cy),
        ]
        pygame.draw.polygon(self.screen, color, points, width)

    def _dashed_circle(
        self,
        color: tuple[int, ...],
        center: tuple[float, float],
        radius: float,
        width: int = 2,
        segments: int = 36,
        phase: float = 0.0,
    ) -> None:
        if radius <= 0:
            return
        cx, cy = center
        for index in range(0, segments, 2):
            start = math.tau * (index + phase) / segments
            end = math.tau * (index + 1 + phase) / segments
            p0 = (
                int(cx + math.cos(start) * radius),
                int(cy + math.sin(start) * radius),
            )
            p1 = (
                int(cx + math.cos(end) * radius),
                int(cy + math.sin(end) * radius),
            )
            pygame.draw.line(self.screen, color, p0, p1, width)

    def _dotted_line(
        self,
        color: tuple[int, ...],
        start: tuple[int, int],
        end: tuple[int, int],
        segments: int = 20,
    ) -> None:
        for index in range(segments):
            if index % 2:
                continue
            t0 = index / segments
            t1 = (index + 1) / segments
            p0 = (
                int(start[0] + (end[0] - start[0]) * t0),
                int(start[1] + (end[1] - start[1]) * t0),
            )
            p1 = (
                int(start[0] + (end[0] - start[0]) * t1),
                int(start[1] + (end[1] - start[1]) * t1),
            )
            pygame.draw.line(self.screen, color, p0, p1, 2)

    def _health_bar(
        self,
        center_x: float,
        top: float,
        width: int,
        hp: int,
        max_hp: int,
        color: tuple[int, ...],
    ) -> None:
        if max_hp <= 0:
            return
        rect = pygame.Rect(int(center_x - width / 2), int(top), width, 4)
        pygame.draw.rect(self.screen, (8, 12, 18), rect)
        ratio = max(0.0, min(1.0, hp / max_hp))
        fill = rect.copy()
        fill.width = int(rect.width * ratio)
        if fill.width > 0:
            pygame.draw.rect(self.screen, color, fill)
        pygame.draw.rect(self.screen, (0, 0, 0), rect, 1)

    # ------------------------------------------------------------------
    # Field elements
    # ------------------------------------------------------------------
    def _build_brick_image(self) -> pygame.Surface:
        image = pygame.Surface((config.TILE, config.TILE))
        rect = image.get_rect()
        image.fill((88, 46, 38))
        for row in range(4):
            y = row * 12
            shift = 12 if row % 2 else 0
            for column in range(-1, 3):
                bx = column * 24 + shift
                brick = pygame.Rect(bx + 1, y + 1, 22, 10).clip(rect)
                if brick.width <= 1 or brick.height <= 1:
                    continue
                shade = 1.0 if (row + column) % 2 == 0 else 0.84
                pygame.draw.rect(
                    image, _scale(config.BRICK, shade), brick
                )
                pygame.draw.line(
                    image,
                    _scale(config.BRICK, 1.25),
                    (brick.left, brick.top),
                    (brick.right - 1, brick.top),
                )
        pygame.draw.rect(image, (54, 30, 26), rect, 1)
        return image

    def _build_steel_image(self) -> pygame.Surface:
        image = pygame.Surface((config.TILE, config.TILE))
        rect = image.get_rect()
        image.fill(_STEEL_DARK)
        inner = rect.inflate(-6, -6)
        pygame.draw.rect(image, config.STEEL, inner, border_radius=3)
        pygame.draw.line(
            image,
            _STEEL_HIGHLIGHT,
            (inner.left + 2, inner.top + 2),
            (inner.right - 2, inner.top + 2),
            2,
        )
        pygame.draw.line(
            image,
            _STEEL_HIGHLIGHT,
            (inner.left + 2, inner.top + 2),
            (inner.left + 2, inner.bottom - 2),
            2,
        )
        pygame.draw.line(
            image,
            _STEEL_SHADOW,
            (inner.left + 2, inner.bottom - 2),
            (inner.right - 2, inner.bottom - 2),
            2,
        )
        pygame.draw.line(
            image,
            _STEEL_SHADOW,
            (inner.right - 2, inner.top + 2),
            (inner.right - 2, inner.bottom - 2),
            2,
        )
        pygame.draw.rect(
            image, _HOLO_EDGE, inner, width=1, border_radius=3
        )
        for corner in (
            (inner.left + 5, inner.top + 5),
            (inner.right - 5, inner.top + 5),
            (inner.left + 5, inner.bottom - 5),
            (inner.right - 5, inner.bottom - 5),
        ):
            pygame.draw.circle(image, (230, 245, 255), corner, 1)
        return image

    def _build_steel_glow_image(self) -> pygame.Surface:
        image = pygame.Surface((config.TILE, config.TILE))
        image.fill((0, 0, 0))
        for index, factor in enumerate((0.18, 0.32, 0.5)):
            inset = index * 3
            glow_rect = pygame.Rect(
                inset,
                inset,
                config.TILE - inset * 2,
                config.TILE - inset * 2,
            )
            pygame.draw.rect(
                image,
                _scale((84, 146, 186), 0.2 * factor),
                glow_rect,
                width=3,
                border_radius=4,
            )
        return image

    def _ensure_wall_layer(self, world) -> None:
        signature = tuple(tuple(row) for row in world.grid)
        if signature == self._wall_signature:
            return
        self._wall_signature = signature
        self._wall_surface = pygame.Surface(
            (config.PLAYFIELD_WIDTH, config.PLAYFIELD_HEIGHT),
            pygame.SRCALPHA,
        )
        self._wall_glow = pygame.Surface(
            (config.PLAYFIELD_WIDTH, config.PLAYFIELD_HEIGHT)
        )
        self._wall_glow.fill((0, 0, 0))
        for ty, row in enumerate(world.grid):
            for tx, tile in enumerate(row):
                if tile == config.Tile.EMPTY:
                    continue
                position = (tx * config.TILE, ty * config.TILE)
                if tile == config.Tile.BRICK:
                    self._wall_surface.blit(self._brick_image, position)
                else:
                    self._wall_surface.blit(self._steel_image, position)
                    self._wall_glow.blit(
                        self._steel_glow_image,
                        position,
                        special_flags=pygame.BLEND_RGB_ADD,
                    )

    def _draw_tiles(self, world, offset: tuple[int, int]) -> None:
        self._ensure_wall_layer(world)
        position = (
            config.PLAYFIELD_X + offset[0],
            config.PLAYFIELD_Y + offset[1],
        )
        self._glow.blit(
            self._wall_glow,
            position,
            special_flags=pygame.BLEND_RGB_ADD,
        )
        self.screen.blit(self._wall_surface, position)

    def _tank_surface(
        self,
        size: int,
        body: tuple[int, ...],
        accent: tuple[int, ...],
        elite: bool,
    ) -> pygame.Surface:
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        dark = _scale(body, 0.36)
        light = _scale(body, 1.3)
        tread_width = max(5, int(size * 0.22))
        for tread_x in (
            int(size * 0.02),
            size - tread_width - int(size * 0.02),
        ):
            tread = pygame.Rect(
                tread_x, int(size * 0.10), tread_width, int(size * 0.78)
            )
            pygame.draw.rect(surface, dark, tread, border_radius=3)
            for index in range(4):
                notch_y = tread.top + 4 + index * max(
                    4, tread.height // 5
                )
                pygame.draw.line(
                    surface,
                    _scale(body, 0.55),
                    (tread.left + 2, notch_y),
                    (tread.right - 2, notch_y),
                    1,
                )

        hull = pygame.Rect(
            int(size * 0.22),
            int(size * 0.18),
            int(size * 0.56),
            int(size * 0.68),
        )
        pygame.draw.rect(
            surface, dark, hull.inflate(2, 2), border_radius=5
        )
        pygame.draw.rect(surface, body, hull, border_radius=4)
        pygame.draw.rect(surface, light, hull, width=1, border_radius=4)
        pygame.draw.line(
            surface,
            light,
            (hull.left + 4, hull.centery),
            (hull.right - 4, hull.centery),
            1,
        )

        cx, cy = size // 2, int(size * 0.50)
        pygame.draw.circle(surface, dark, (cx, cy), int(size * 0.20))
        pygame.draw.circle(surface, accent, (cx, cy), int(size * 0.17))
        pygame.draw.circle(
            surface, _scale(accent, 0.6), (cx, cy), int(size * 0.17), 1
        )

        barrel_width = max(4, int(size * 0.10))
        pygame.draw.rect(
            surface,
            _scale(accent, 0.9),
            pygame.Rect(
                cx - barrel_width // 2,
                int(size * 0.04),
                barrel_width,
                int(size * 0.44),
            ),
            border_radius=2,
        )
        pygame.draw.rect(
            surface,
            _scale(accent, 1.3),
            pygame.Rect(
                cx - barrel_width // 2,
                int(size * 0.04),
                max(1, barrel_width // 2),
                int(size * 0.44),
            ),
        )
        pygame.draw.circle(
            surface,
            (240, 250, 255),
            (cx, cy),
            max(2, int(size * 0.045)),
        )
        if elite:
            pygame.draw.circle(
                surface, _ELITE_LIGHT, (cx, cy), int(size * 0.22), 1
            )
        return surface

    def _draw_tank(
        self,
        pos: pygame.Vector2,
        size: int,
        direction: config.Direction,
        body: tuple[int, ...],
        accent: tuple[int, ...],
        offset: tuple[int, int],
        elite: bool = False,
        glow_strength: float = 0.5,
    ) -> None:
        key = (size, tuple(body), tuple(accent), elite, int(direction))
        surface = self._tank_cache.get(key)
        if surface is None:
            base = self._tank_surface(size, body, accent, elite)
            surface = pygame.transform.rotate(base, -direction.angle)
            self._tank_cache[key] = surface
        center = (
            int(pos[0] + offset[0]),
            int(pos[1] + offset[1]),
        )
        rect = surface.get_rect(center=center)
        self.screen.blit(surface, rect)
        self._glow_circle(body, center, size * 0.85, strength=glow_strength)

    def _draw_base(self, world, offset: tuple[int, int]) -> None:
        base = world.base
        rect = base.rect.move(offset)
        alive = base.alive
        core_color = (168, 226, 255) if alive else (210, 80, 80)
        self._glow_rect(core_color, rect.inflate(18, 18), 0.5)

        pygame.draw.rect(self.screen, (22, 32, 44), rect)
        inner = rect.inflate(-10, -10)
        pygame.draw.rect(
            self.screen, (58, 78, 98), inner, border_radius=4
        )
        pygame.draw.line(
            self.screen,
            (28, 40, 54),
            (inner.centerx, inner.top),
            (inner.centerx, inner.bottom),
            2,
        )
        pygame.draw.line(
            self.screen,
            (28, 40, 54),
            (inner.left, inner.centery),
            (inner.right, inner.centery),
            2,
        )
        pygame.draw.line(
            self.screen,
            _STEEL_HIGHLIGHT,
            (inner.left + 2, inner.top + 2),
            (inner.right - 2, inner.top + 2),
            2,
        )
        pygame.draw.rect(
            self.screen, _HOLO_EDGE, rect, width=2, border_radius=4
        )

        pulse = 0.5 + 0.5 * math.sin(world.elapsed * 3.0)
        center = rect.center
        self._diamond(center, 16 + int(2 * pulse), core_color)
        self._diamond(center, 9, (18, 36, 50))
        self._glow_circle(core_color, center, 36, strength=0.55)

        pip_width = base.max_hp * 14
        start_x = rect.centerx - pip_width // 2 + 7
        for index in range(base.max_hp):
            pip_center = (start_x + index * 14, rect.top - 10)
            pip_color = (
                (204, 244, 255) if index < base.hp else (56, 68, 82)
            )
            self._diamond(pip_center, 5, pip_color)

        if base.shield > 0:
            radius = rect.width // 2 + 8
            pygame.draw.circle(
                self.screen, (84, 226, 238), center, radius, 2
            )
            self._glow_circle(
                (72, 220, 240), center, radius + 4, strength=0.5
            )
            self._text(
                self.tr("hud.shield", value=base.shield),
                self.font_xs,
                (136, 240, 248),
                (center[0], rect.top - 28),
                align="center",
            )

        if not alive:
            pygame.draw.line(
                self.screen,
                (226, 72, 72),
                (rect.left + 14, rect.top + 14),
                (rect.right - 14, rect.bottom - 14),
                4,
            )
            pygame.draw.line(
                self.screen,
                (226, 72, 72),
                (rect.right - 14, rect.top + 14),
                (rect.left + 14, rect.bottom - 14),
                4,
            )

    def _draw_players(self, world, offset: tuple[int, int]) -> None:
        ox, oy = offset
        for player in world.players:
            color = (
                config.P1_BLUE
                if player.player_id == 0
                else config.P2_AMBER
            )
            accent = _scale(color, 1.4)
            center = (
                int(player.pos.x + ox),
                int(player.pos.y + oy),
            )
            if player.alive and not player.eliminated:
                self._draw_tank(
                    player.pos,
                    player.rect.width,
                    player.direction,
                    color,
                    accent,
                    offset,
                    glow_strength=0.45,
                )
                if player.hp < player.max_hp:
                    self._health_bar(
                        center[0],
                        player.rect.top + oy - 8,
                        32,
                        player.hp,
                        player.max_hp,
                        color,
                    )
                if player.invuln > 0:
                    radius = (
                        player.rect.width // 2
                        + 6
                        + int(2 * math.sin(world.elapsed * 18.0))
                    )
                    pygame.draw.circle(
                        self.screen, (232, 250, 255), center, radius, 1
                    )
                    self._glow_circle(
                        color, center, radius + 4, strength=0.35
                    )
            elif not player.eliminated:
                pygame.draw.circle(
                    self.screen, _scale(color, 0.65), center, 16, 1
                )
                self._text(
                    self.tr(
                        "hud.player_respawn",
                        number=player.player_id + 1,
                        seconds=player.respawn_timer,
                    ),
                    self.font_xs,
                    color,
                    (center[0], center[1] - 26),
                    align="center",
                )
                self._glow_circle(color, center, 28, strength=0.2)

    def _draw_enemies(self, world, offset: tuple[int, int]) -> None:
        ox, oy = offset
        for enemy in world.enemies:
            if not enemy.alive:
                continue
            elite = enemy.kind == "elite"
            if elite:
                body = _ELITE_MAGENTA
                accent = _ELITE_LIGHT
            elif enemy.kind == "gunner":
                body = config.ENEMY_ORANGE
                accent = (255, 214, 150)
            elif enemy.kind == "demolisher":
                body = _ENEMY_DEMOLISHER
                accent = (255, 178, 96)
            else:
                body = config.ENEMY_RED
                accent = (255, 156, 146)

            center = (
                int(enemy.pos.x + ox),
                int(enemy.pos.y + oy),
            )
            self._draw_tank(
                enemy.pos,
                enemy.rect.width,
                enemy.direction,
                body,
                accent,
                offset,
                elite=elite,
                glow_strength=0.5,
            )
            if enemy.max_hp > 1:
                self._health_bar(
                    center[0],
                    enemy.rect.top + oy - 8,
                    28,
                    enemy.hp,
                    enemy.max_hp,
                    body,
                )
            if elite:
                shield = getattr(enemy, "shield", 0)
                if shield > 0:
                    radius = enemy.rect.width // 2 + 5
                    pygame.draw.circle(
                        self.screen, (120, 240, 255), center, radius, 2
                    )
                    self._glow_circle(
                        (80, 220, 255), center, radius + 4, strength=0.4
                    )
                    self._text(
                        str(shield),
                        self.font_xs,
                        (184, 250, 255),
                        (center[0], center[1] - radius - 8),
                        align="center",
                    )
            if (
                enemy.kind == "elite"
                and getattr(enemy, "telegraph", 0.0) > 0.0
            ):
                pending = getattr(enemy, "pending_spread", None)
                warn_direction = pending or enemy.direction
                warn_color = (255, 76, 112)
                radius = enemy.rect.width // 2 + 9
                pygame.draw.circle(
                    self.screen, warn_color, center, radius, 2
                )
                self._glow_circle(
                    warn_color, center, radius + 3, strength=0.35
                )
                dx, dy = warn_direction.vector
                tip = (
                    center[0] + dx * (radius + 16),
                    center[1] + dy * (radius + 16),
                )
                self._glow_line(
                    (255, 112, 150), center, tip, width=4, strength=0.5
                )
            if enemy.kind == "demolisher" and getattr(
                enemy, "telegraph", 0.0
            ) > 0.0:
                self._dashed_circle(
                    (255, 122, 62),
                    center,
                    config.DEMOLISHER_BLAST_RADIUS,
                    2,
                    40,
                    world.elapsed * 2.0,
                )
                self._glow_circle(
                    (255, 110, 60),
                    center,
                    config.DEMOLISHER_BLAST_RADIUS,
                    strength=0.18,
                )

    def _draw_boss(self, world, offset: tuple[int, int]) -> None:
        boss = world.boss
        if boss is None or not boss.alive:
            return

        ox, oy = offset
        cx = int(boss.pos.x + ox)
        cy = int(boss.pos.y + oy)
        size = config.BOSS_SIZE
        phase_color = _BOSS_PHASE_COLORS.get(
            boss.phase, _BOSS_PHASE_COLORS[1]
        )
        pulse = 0.5 + 0.5 * math.sin(world.elapsed * 4.0)

        self._glow_circle(
            phase_color, (cx, cy), size * 0.82, strength=0.45 + 0.2 * pulse
        )

        for tread_x in (cx - size // 2 + 6, cx + size // 2 - 22):
            tread = pygame.Rect(
                tread_x, cy - size // 2 + 12, 16, int(size * 0.72)
            )
            pygame.draw.rect(
                self.screen, (22, 26, 34), tread, border_radius=4
            )
            for index in range(5):
                notch_y = tread.top + 8 + index * (tread.height // 6)
                pygame.draw.line(
                    self.screen,
                    (52, 60, 72),
                    (tread.left + 2, notch_y),
                    (tread.right - 2, notch_y),
                    1,
                )

        hull = [
            (cx - 32, cy - 34),
            (cx + 32, cy - 34),
            (cx + 44, cy),
            (cx + 32, cy + 34),
            (cx - 32, cy + 34),
            (cx - 44, cy),
        ]
        inner_hull = [
            (cx - 26, cy - 27),
            (cx + 26, cy - 27),
            (cx + 35, cy),
            (cx + 26, cy + 27),
            (cx - 26, cy + 27),
            (cx - 35, cy),
        ]
        pygame.draw.polygon(self.screen, (48, 58, 74), hull)
        pygame.draw.polygon(self.screen, (26, 34, 46), inner_hull)
        pygame.draw.polygon(self.screen, phase_color, hull, 2)

        barrel = pygame.Rect(cx - 8, cy, 16, size // 2 - 16)
        pygame.draw.rect(
            self.screen,
            _scale(phase_color, 0.75),
            barrel,
            border_radius=3,
        )
        pygame.draw.rect(
            self.screen,
            _scale(phase_color, 1.1),
            pygame.Rect(cx - 8, cy, 6, size // 2 - 16),
            border_radius=2,
        )

        pygame.draw.circle(self.screen, (62, 72, 90), (cx, cy), 30)
        pygame.draw.circle(
            self.screen, _scale(phase_color, 0.9), (cx, cy), 26
        )
        pygame.draw.circle(self.screen, (20, 28, 38), (cx, cy), 18)
        core_radius = 10 + int(3 * pulse)
        pygame.draw.circle(
            self.screen, phase_color, (cx, cy), core_radius
        )
        pygame.draw.circle(
            self.screen,
            (250, 250, 255),
            (cx, cy),
            max(3, core_radius // 3),
        )
        self._glow_circle(phase_color, (cx, cy), 52, strength=0.7)

        if boss.phase_flash > 0.0:
            pygame.draw.polygon(self.screen, (255, 255, 255), hull, 3)

        self._health_bar(
            cx,
            max(8, cy - size // 2 - 18),
            size - 12,
            boss.hp,
            boss.max_hp,
            phase_color,
        )
        self._text(
            self.tr("hud.phase", phase=boss.phase),
            self.font_xs,
            (214, 232, 246),
            (cx, cy + size // 2 + 12),
            align="center",
        )
        self._draw_boss_telegraph(world, boss, (cx, cy), phase_color, offset)

    def _draw_boss_telegraph(
        self,
        world,
        boss,
        center: tuple[int, int],
        phase_color: tuple[int, ...],
        offset: tuple[int, int],
    ) -> None:
        kind = boss.telegraph_kind
        if not kind or boss.telegraph <= 0.0:
            return
        cx, cy = center
        ox, oy = offset
        if kind == "aimed" and boss.telegraph_target is not None:
            end = (
                int(boss.telegraph_target.x + ox),
                int(boss.telegraph_target.y + oy),
            )
            self._dotted_line((255, 138, 84), center, end, 18)
            pygame.draw.circle(self.screen, (255, 152, 92), end, 13, 2)
            pygame.draw.line(
                self.screen,
                (255, 196, 150),
                (end[0] - 18, end[1]),
                (end[0] + 18, end[1]),
                1,
            )
            pygame.draw.line(
                self.screen,
                (255, 196, 150),
                (end[0], end[1] - 18),
                (end[0], end[1] + 18),
                1,
            )
            self._glow_circle((255, 112, 62), end, 24, strength=0.5)
        elif kind == "radial":
            radius = 42 + int(22 * (1.0 - min(1.0, boss.telegraph)))
            self._dashed_circle(
                (255, 154, 84),
                center,
                radius,
                2,
                34,
                world.elapsed * 2.0,
            )
            self._glow_circle(
                (255, 122, 64), center, radius, strength=0.25
            )
        elif kind == "laser":
            direction = boss.telegraph_direction
            if direction is None:
                direction = config.Direction.DOWN
            dx, dy = direction.vector
            length = max(config.PLAYFIELD_WIDTH, config.PLAYFIELD_HEIGHT)
            end = (cx + dx * length, cy + dy * length)
            self._glow_line(
                (255, 84, 84), center, end, width=10, strength=0.55
            )
            self._dotted_line((255, 196, 196), center, end, 24)
            self._glow_circle(phase_color, center, 54, strength=0.5)

    def _draw_projectiles(self, world, offset: tuple[int, int]) -> None:
        ox, oy = offset
        for bullet in world.bullets:
            if not bullet.alive:
                continue
            if bullet.friendly:
                if bullet.owner_id == 0:
                    color = config.P1_BLUE
                elif bullet.owner_id == 1:
                    color = config.P2_AMBER
                else:
                    color = (150, 220, 255)
            else:
                color = (255, 110, 80)
            center = (
                int(bullet.pos.x + ox),
                int(bullet.pos.y + oy),
            )
            self._glow_circle(color, center, 14, strength=0.7)
            if bullet.prev_pos != bullet.pos:
                prev = (
                    int(bullet.prev_pos.x + ox),
                    int(bullet.prev_pos.y + oy),
                )
                self._glow_line(color, prev, center, 4, strength=0.5)
            pygame.draw.circle(self.screen, color, center, 5)
            pygame.draw.circle(
                self.screen, (248, 252, 255), center, 2
            )

        for laser in world.lasers:
            intensity = max(
                0.0, min(1.0, laser.life / max(config.LASER_LIFE, 0.001))
            )
            if intensity <= 0.0:
                continue
            start = (
                int(laser.origin.x + ox),
                int(laser.origin.y + oy),
            )
            end = (
                int(laser.end.x + ox),
                int(laser.end.y + oy),
            )
            self._glow_line(
                (110, 190, 255), start, end, 20 * intensity, 0.9
            )
            self._glow_line(
                (190, 235, 255), start, end, 8 * intensity, 1.0
            )
            pygame.draw.line(
                self.screen,
                (224, 246, 255),
                start,
                end,
                max(2, int(5 * intensity)),
            )
            pygame.draw.line(
                self.screen, (255, 255, 255), start, end, 1
            )
            self._glow_circle((210, 244, 255), end, 22, strength=0.7)

        for grenade in world.grenades:
            self._draw_grenade(grenade, world, offset)

    def _draw_grenade(self, grenade, world, offset: tuple[int, int]) -> None:
        ox, oy = offset
        owner = grenade.owner_id
        color = (
            config.P1_BLUE
            if owner == 0
            else config.P2_AMBER
            if owner == 1
            else config.ENEMY_ORANGE
        )
        start = grenade.start
        target = grenade.target
        for index in range(1, 13):
            t = index / 13.0
            px = start.x + (target.x - start.x) * t + ox
            py = start.y + (target.y - start.y) * t + oy
            py -= 4.0 * config.GRENADE_ARC_HEIGHT * t * (1.0 - t)
            pygame.draw.circle(
                self.screen, _scale(color, 0.7), (int(px), int(py)), 2
            )

        target_point = (
            int(target.x + ox),
            int(target.y + oy),
        )
        self._dashed_circle(
            _scale(color, 0.75),
            target_point,
            grenade.radius,
            1,
            44,
            world.elapsed * 1.5,
        )
        pygame.draw.circle(
            self.screen, _scale(color, 0.9), target_point, 9, 2
        )
        pygame.draw.line(
            self.screen,
            _scale(color, 0.9),
            (target_point[0] - 13, target_point[1]),
            (target_point[0] + 13, target_point[1]),
            1,
        )
        pygame.draw.line(
            self.screen,
            _scale(color, 0.9),
            (target_point[0], target_point[1] - 13),
            (target_point[0], target_point[1] + 13),
            1,
        )

        position = grenade.position()
        center = (
            int(position.x + ox),
            int(position.y + oy - grenade.height()),
        )
        self._glow_circle(color, center, 18, strength=0.7)
        pygame.draw.circle(self.screen, color, center, 5)
        pygame.draw.circle(self.screen, (255, 255, 255), center, 2)

    def _draw_particle_glow(self, world, offset: tuple[int, int]) -> None:
        ox, oy = offset
        for particle in world.effects.particles:
            ratio = (
                particle.life / particle.max_life
                if particle.max_life > 0.0
                else 0.0
            )
            center = (
                int(particle.pos.x + ox),
                int(particle.pos.y + oy),
            )
            radius = max(2.0, particle.size * ratio * 2.4)
            self._glow_circle(
                particle.color, center, radius, strength=0.45 * ratio
            )

    # ------------------------------------------------------------------
    # HUD
    # ------------------------------------------------------------------
    def _hud_rects(self) -> tuple[pygame.Rect, ...]:
        top = self.hud_rect.top + _HUD_INNER_Y
        scale = self.width / 1280.0
        specs = (
            (12, 280),
            (304, 280),
            (596, 120),
            (724, 180),
            (912, 240),
            (1164, 102),
        )
        rects = []
        for x, width in specs:
            rects.append(
                pygame.Rect(
                    int(x * scale),
                    top,
                    int(width * scale),
                    _HUD_CARD_HEIGHT,
                )
            )
        return tuple(rects)

    def _draw_hud(self, world) -> None:
        pygame.draw.rect(self.screen, (8, 12, 18), self.hud_rect)
        pygame.draw.line(
            self.screen,
            (34, 82, 108),
            (self.hud_rect.left, self.hud_rect.top),
            (self.hud_rect.right, self.hud_rect.top),
            2,
        )
        for y in range(self.hud_rect.top + 3, self.hud_rect.bottom, 4):
            pygame.draw.line(
                self.screen,
                (11, 17, 24),
                (self.hud_rect.left, y),
                (self.hud_rect.right, y),
            )

        cards = self._hud_rects()
        for index, player in enumerate(world.players[:2]):
            self._draw_player_card(player, cards[index])
        self._draw_revives(world, cards[2])
        self._draw_base_hud(world, cards[3])
        self._draw_level_track(world, cards[4])
        self._draw_enemy_counter(world, cards[5])

    def _draw_player_card(self, player, rect: pygame.Rect) -> None:
        color = (
            config.P1_BLUE if player.player_id == 0 else config.P2_AMBER
        )
        self._panel(
            rect, fill=_HUD_PANEL, border=_scale(color, 0.45), accent=color
        )
        self._text(
            self.tr("hud.player", number=player.player_id + 1),
            self.font_m,
            color,
            (rect.left + 10, rect.top + 3),
        )
        self._text(
            self.tr(
                "hud.hp", current=player.hp, maximum=player.max_hp
            ),
            self.font_xs,
            _HUD_TEXT,
            (rect.left + 48, rect.top + 9),
        )

        if player.eliminated:
            status, status_color = self.tr("hud.eliminated"), (220, 110, 110)
        elif not player.alive:
            status = self.tr(
                "hud.respawn", seconds=player.respawn_timer
            )
            status_color = color
        else:
            status, status_color = self.tr("hud.online"), (150, 216, 190)
        self._text(
            status,
            self.font_xs,
            status_color,
            (rect.right - 8, rect.top + 9),
            align="right",
        )

        hp_bar = pygame.Rect(rect.left + 8, rect.top + 27, rect.width - 16, 8)
        pygame.draw.rect(self.screen, (18, 26, 36), hp_bar, border_radius=3)
        ratio = (
            max(0.0, min(1.0, player.hp / player.max_hp))
            if player.max_hp > 0
            else 0.0
        )
        hp_fill = hp_bar.copy()
        hp_fill.width = int(hp_bar.width * ratio)
        if hp_fill.width > 0:
            pygame.draw.rect(
                self.screen, color, hp_fill, border_radius=3
            )
        pygame.draw.rect(
            self.screen, _scale(color, 0.6), hp_bar, 1, border_radius=3
        )

        if player.player_id == 0:
            self._draw_cooldown(
                rect,
                rect.top + 48,
                self.tr("hud.grenade"),
                player.grenade_timer,
                player.stats.grenade_cooldown,
                color,
                player.eliminated,
            )
        else:
            self._draw_cooldown(
                rect,
                rect.top + 48,
                self.tr("hud.laser"),
                player.laser_timer,
                player.stats.laser_cooldown,
                color,
                player.eliminated,
            )

    def _draw_cooldown(
        self,
        rect: pygame.Rect,
        y: int,
        label: str,
        remaining: float,
        cooldown: float,
        color: tuple[int, ...],
        eliminated: bool,
    ) -> None:
        self._text(
            label,
            self.font_xs,
            _HUD_MUTED,
            (rect.left + 8, y - 4),
        )
        bar = pygame.Rect(rect.left + 40, y, rect.width - 48, 7)
        pygame.draw.rect(self.screen, (18, 26, 36), bar, border_radius=3)
        ratio = 1.0
        if cooldown > 0.0:
            ratio = 1.0 - max(0.0, min(1.0, remaining / cooldown))
        if eliminated:
            ratio = 0.0
        fill = bar.copy()
        fill.width = int(bar.width * ratio)
        if fill.width > 0:
            fill_color = color if ratio >= 1.0 else _scale(color, 0.55)
            pygame.draw.rect(
                self.screen, fill_color, fill, border_radius=3
            )
        pygame.draw.rect(
            self.screen, _scale(color, 0.4), bar, 1, border_radius=3
        )

    def _draw_revives(self, world, rect: pygame.Rect) -> None:
        self._panel(rect, fill=_HUD_PANEL, border=_HUD_BORDER)
        self._text(
            self.tr("hud.revive"),
            self.font_xs,
            _HUD_MUTED,
            (rect.centerx, rect.top + 9),
            align="center",
        )
        count = max(0, int(world.shared_lives))
        shown = min(count, 6)
        if shown == 0:
            self._diamond(
                (rect.centerx, rect.top + 38), 7, (58, 72, 88), 1
            )
        else:
            gap = 16 if shown <= 3 else 13
            start = rect.centerx - (shown - 1) * gap / 2
            for index in range(shown):
                self._diamond(
                    (start + index * gap, rect.top + 36),
                    6,
                    _REVIVE_DIAMOND,
                )
        if count > shown:
            self._text(
                self.tr("hud.revive_extra", count=count - shown),
                self.font_xs,
                _REVIVE_DIAMOND,
                (rect.centerx, rect.top + 53),
                align="center",
            )
        else:
            self._text(
                self.tr("hud.revive_count", count=count),
                self.font_xs,
                _HUD_MUTED,
                (rect.centerx, rect.top + 54),
                align="center",
            )

    def _draw_base_hud(self, world, rect: pygame.Rect) -> None:
        base = world.base
        self._panel(rect, fill=_HUD_PANEL, border=_HUD_BORDER)
        self._text(
            self.tr("hud.base"),
            self.font_xs,
            _HUD_MUTED,
            (rect.left + 8, rect.top + 8),
        )
        shield_text = (
            self.tr("hud.shield", value=base.shield)
            if base.shield > 0
            else self.tr("hud.shield_none")
        )
        self._text(
            shield_text,
            self.font_xs,
            (120, 230, 244) if base.shield > 0 else _HUD_MUTED,
            (rect.right - 8, rect.top + 8),
            align="right",
        )

        bar = pygame.Rect(rect.left + 8, rect.top + 30, rect.width - 16, 10)
        pygame.draw.rect(self.screen, (18, 26, 36), bar, border_radius=3)
        ratio = (
            max(0.0, min(1.0, base.hp / base.max_hp))
            if base.max_hp > 0
            else 0.0
        )
        fill = bar.copy()
        fill.width = int(bar.width * ratio)
        hp_color = (196, 238, 255) if base.alive else (210, 80, 80)
        if fill.width > 0:
            pygame.draw.rect(
                self.screen, hp_color, fill, border_radius=3
            )
        pygame.draw.rect(
            self.screen, _scale(hp_color, 0.5), bar, 1, border_radius=3
        )

        for index in range(base.max_hp):
            center = (rect.left + 14 + index * 16, rect.top + 55)
            pip_color = (
                hp_color if index < base.hp else (52, 64, 78)
            )
            self._diamond(center, 5, pip_color)
        state = (
            self.tr("hud.online")
            if base.alive
            else self.tr("hud.destroyed")
        )
        self._text(
            state,
            self.font_xs,
            (150, 216, 190) if base.alive else (220, 110, 110),
            (rect.right - 8, rect.top + 49),
            align="right",
        )

    def _draw_level_track(self, world, rect: pygame.Rect) -> None:
        self._panel(rect, fill=_HUD_PANEL, border=_HUD_BORDER)
        current = int(world.level_index)
        self._text(
            self.tr("hud.level"),
            self.font_xs,
            _HUD_MUTED,
            (rect.left + 8, rect.top + 8),
        )
        self._text(
            f"{current + 1}/{config.LEVEL_COUNT}",
            self.font_xs,
            _HUD_TEXT,
            (rect.right - 8, rect.top + 8),
            align="right",
        )
        track_left = rect.left + 16
        track_right = rect.right - 16
        y = rect.top + 42
        spacing = (track_right - track_left) / (config.LEVEL_COUNT - 1)
        pygame.draw.line(
            self.screen,
            (36, 58, 76),
            (track_left, y),
            (track_right, y),
            2,
        )
        for index in range(config.LEVEL_COUNT):
            x = int(track_left + index * spacing)
            is_boss = index == config.BOSS_LEVEL
            if index < current:
                color = config.HOLO_WHITE
                radius = 5
            elif index == current:
                color = _ELITE_MAGENTA if is_boss else config.P1_BLUE
                radius = 7
                pygame.draw.circle(
                    self.screen, _scale(color, 0.18), (x, y), 14
                )
                pygame.draw.circle(
                    self.screen, _scale(color, 0.34), (x, y), 10
                )
            else:
                color = (52, 70, 88)
                radius = 4
            pygame.draw.circle(self.screen, color, (x, y), radius)
            if index == current:
                pygame.draw.circle(
                    self.screen, (240, 250, 255), (x, y), radius, 1
                )
            if is_boss:
                pygame.draw.circle(
                    self.screen, _ELITE_MAGENTA, (x, y), 9, 1
                )
        status = (
            self.tr("hud.boss")
            if current == config.BOSS_LEVEL
            else self.tr("hud.field")
        )
        self._text(
            status,
            self.font_xs,
            _HUD_MUTED,
            (rect.centerx, rect.top + 57),
            align="center",
        )

    def _draw_enemy_counter(self, world, rect: pygame.Rect) -> None:
        self._panel(rect, fill=_HUD_PANEL, border=_HUD_BORDER)
        boss_level = world.boss is not None and world.boss.alive
        label = (
            self.tr("hud.boss") if boss_level else self.tr("hud.enemy")
        )
        self._text(
            label,
            self.font_xs,
            _ELITE_MAGENTA if boss_level else _HUD_MUTED,
            (rect.centerx, rect.top + 9),
            align="center",
        )
        remaining = max(0, int(world.remaining_enemies))
        color = (
            _ELITE_MAGENTA
            if boss_level
            else config.ENEMY_RED
            if remaining > 0
            else config.HOLO_WHITE
        )
        self._text(
            str(remaining),
            self.font_l,
            color,
            (rect.centerx, rect.top + 42),
            align="center",
        )

    # ------------------------------------------------------------------
    # Public drawing API
    # ------------------------------------------------------------------
    def draw_world(self, world) -> None:
        self.screen.blit(self._background, (0, 0))
        offset = world.effects.offset()

        self._begin_glow()
        self._draw_tiles(world, offset)
        self._draw_base(world, offset)
        self._draw_players(world, offset)
        self._draw_enemies(world, offset)
        self._draw_boss(world, offset)
        self._draw_projectiles(world, offset)
        self._draw_particle_glow(world, offset)
        self._end_glow()

        world.effects.draw(self.screen, offset)
        self._draw_hud(world)

    def draw_title(self, t: float, difficulty: str = "normal") -> None:
        self.screen.blit(self._background, (0, 0))
        self._dim(148)
        cx, cy = self.width // 2, 220
        pulse = 0.5 + 0.5 * math.sin(t * 2.4)

        self._begin_glow()
        self._glow_circle(
            config.P1_BLUE, (cx, cy), 230, strength=0.25 + 0.18 * pulse
        )
        self._glow_circle(config.P2_AMBER, (cx, cy), 130, strength=0.18)
        self._end_glow()

        for index in range(4):
            radius = 106 + index * 44 + int(8 * pulse)
            pygame.draw.circle(
                self.screen,
                _scale(config.P1_BLUE, 0.3),
                (cx, cy),
                radius,
                1,
            )
        self._text(
            "BATTLE CITY",
            self.font_xl,
            (232, 248, 255),
            (cx, cy),
            align="center",
        )
        self._text(
            self.tr("title.subtitle"),
            self.font_m,
            config.P2_AMBER,
            (cx, cy + 58),
            align="center",
        )
        pygame.draw.line(
            self.screen,
            config.P1_BLUE,
            (cx - 230, cy + 92),
            (cx - 42, cy + 92),
            2,
        )
        pygame.draw.line(
            self.screen,
            config.P2_AMBER,
            (cx + 42, cy + 92),
            (cx + 230, cy + 92),
            2,
        )
        prompt_color = (
            config.HOLO_WHITE
            if int(t * 2) % 2 == 0
            else _scale(config.HOLO_WHITE, 0.45)
        )
        self._text(
            self.tr("title.start"),
            self.font_m,
            prompt_color,
            (cx, cy + 156),
            align="center",
        )
        self._text(
            self.tr("title.tagline"),
            self.font_s,
            (126, 164, 192),
            (cx, cy + 204),
            align="center",
        )
        difficulty_name = self.tr(f"difficulty.{str(difficulty).lower()}")
        difficulty_color = (
            config.ENEMY_RED
            if str(difficulty).lower() == "hell"
            else config.P1_BLUE
        )
        self._text(
            self.tr("title.difficulty", name=difficulty_name),
            self.font_m,
            difficulty_color,
            (cx, cy + 244),
            align="center",
        )
        self._text(
            self.tr("title.difficulty_hint"),
            self.font_s,
            (126, 164, 192),
            (cx, cy + 280),
            align="center",
        )
        self._text(
            self.tr(
                "title.language",
                name=self.tr(f"language.{self.language}"),
            ),
            self.font_m,
            config.P2_AMBER,
            (cx, cy + 316),
            align="center",
        )
        self._text(
            self.tr("title.language_hint"),
            self.font_s,
            (126, 164, 192),
            (cx, cy + 352),
            align="center",
        )

    def draw_controls(self) -> None:
        self.screen.blit(self._background, (0, 0))
        self._dim(168)
        cx = self.width // 2
        card = pygame.Rect(cx - 450, 110, 900, 500)
        self._panel(
            card,
            fill=(10, 16, 24),
            border=(58, 106, 136),
            accent=config.P1_BLUE,
        )
        self._text(
            self.tr("controls.title"),
            self.font_xl,
            (232, 248, 255),
            (cx, 178),
            align="center",
        )
        self._text(
            self.tr("controls.subtitle"),
            self.font_s,
            config.P2_AMBER,
            (cx, 224),
            align="center",
        )

        rows = (
            (
                self.tr("controls.p1"),
                config.P1_BLUE,
                self.tr("controls.p1_actions"),
            ),
            (
                self.tr("controls.p2"),
                config.P2_AMBER,
                self.tr("controls.p2_actions"),
            ),
            (
                self.tr("controls.system"),
                (150, 190, 214),
                self.tr("controls.system_actions"),
            ),
        )
        y = 292
        for label, color, text in rows:
            self._text(label, self.font_m, color, (card.left + 46, y))
            self._text(text, self.font_m, _HUD_TEXT, (card.left + 116, y))
            pygame.draw.line(
                self.screen,
                (34, 54, 70),
                (card.left + 40, y + 38),
                (card.right - 40, y + 38),
                1,
            )
            y += 74

        self._text(
            self.tr(
                "controls.language",
                name=self.tr(f"language.{self.language}"),
            ),
            self.font_s,
            config.P2_AMBER,
            (cx, card.bottom - 112),
            align="center",
        )
        self._text(
            self.tr("controls.tip"),
            self.font_s,
            (126, 164, 192),
            (cx, card.bottom - 74),
            align="center",
        )
        self._text(
            self.tr("controls.continue"),
            self.font_m,
            config.HOLO_WHITE,
            (cx, card.bottom - 34),
            align="center",
        )

    def draw_upgrade(
        self,
        offers: list[list[Upgrade]],
        levels: list[dict[str, int]],
        choosing: int,
    ) -> None:
        self._dim(176)
        cx = self.width // 2
        color = (
            config.P1_BLUE if choosing == 0 else config.P2_AMBER
        )
        self._text(
            self.tr("upgrade.choose_title", number=choosing + 1),
            self.font_l,
            color,
            (cx, 88),
            align="center",
        )
        self._text(
            self.tr("upgrade.choose_watch"),
            self.font_s,
            (140, 172, 196),
            (cx, 126),
            align="center",
        )

        current_offers = (
            offers[choosing] if 0 <= choosing < len(offers) else []
        )
        current_levels = (
            levels[choosing] if 0 <= choosing < len(levels) else {}
        )

        card_width = 320
        gap = 34
        total = 3 * card_width + 2 * gap
        start = (self.width - total) // 2
        top = 178
        height = 400
        for index, upgrade in enumerate(current_offers[:3]):
            card = pygame.Rect(
                start + index * (card_width + gap), top, card_width, height
            )
            self._panel(
                card,
                fill=(13, 21, 31),
                border=_scale(color, 0.6),
                accent=color,
            )
            badge = pygame.Rect(card.left + 18, card.top + 18, 42, 42)
            pygame.draw.rect(
                self.screen, _scale(color, 0.28), badge, border_radius=8
            )
            pygame.draw.rect(
                self.screen, color, badge, width=2, border_radius=8
            )
            self._text(
                str(index + 1),
                self.font_l,
                color,
                badge.center,
                align="center",
            )
            self._text(
                self.tr(upgrade.name_key),
                self.font_m,
                (236, 248, 255),
                (card.left + 18, card.top + 76),
            )
            lines = self._wrap_text(
                self.tr(upgrade.desc_key), self.font_s, card_width - 36
            )
            for line_index, line in enumerate(lines[:4]):
                self._text(
                    line,
                    self.font_s,
                    (150, 182, 204),
                    (card.left + 18, card.top + 128 + line_index * 26),
                )

            stacks = current_levels.get(upgrade.id, 0)
            self._text(
                self.tr(
                    "upgrade.stack",
                    current=stacks,
                    maximum=upgrade.max_stacks,
                ),
                self.font_xs,
                color,
                (card.left + 18, card.bottom - 78),
            )
            for stack_index in range(upgrade.max_stacks):
                pip = pygame.Rect(
                    card.left + 18 + stack_index * 26,
                    card.bottom - 52,
                    18,
                    8,
                )
                pip_color = (
                    color if stack_index < stacks else (40, 52, 66)
                )
                pygame.draw.rect(
                    self.screen, pip_color, pip, border_radius=3
                )
            self._text(
                self.tr("upgrade.press", number=index + 1),
                self.font_s,
                (206, 226, 240),
                (card.centerx, card.bottom - 24),
                align="center",
            )

        if not current_offers:
            self._text(
                self.tr("upgrade.none"),
                self.font_m,
                (200, 150, 150),
                (cx, top + height // 2),
                align="center",
            )

    def draw_pause(self) -> None:
        self._dim(158)
        cx = self.width // 2
        card = pygame.Rect(cx - 220, self.height // 2 - 110, 440, 220)
        self._panel(
            card,
            fill=(10, 16, 24),
            border=(58, 106, 136),
            accent=config.P1_BLUE,
        )
        self._begin_glow()
        self._glow_circle(
            config.P1_BLUE, card.center, 150, strength=0.3
        )
        self._end_glow()
        self._text(
            self.tr("pause.title"),
            self.font_xl,
            (232, 248, 255),
            (cx, card.top + 70),
            align="center",
        )
        self._text(
            self.tr("pause.resume"),
            self.font_m,
            config.P1_BLUE,
            (cx, card.top + 128),
            align="center",
        )
        self._text(
            self.tr(
                "pause.language",
                name=self.tr(f"language.{self.language}"),
            ),
            self.font_s,
            config.P2_AMBER,
            (cx, card.top + 158),
            align="center",
        )
        self._text(
            self.tr("pause.subtitle"),
            self.font_s,
            (126, 164, 192),
            (cx, card.top + 190),
            align="center",
        )

    def draw_game_over(self, world, reason: str) -> None:
        self._dim(194)
        cx = self.width // 2
        cy = 246
        self._begin_glow()
        self._glow_circle(
            config.ENEMY_RED, (cx, cy), 240, strength=0.35
        )
        self._end_glow()
        self._text(
            self.tr("gameover.title"),
            self.font_xl,
            (255, 122, 112),
            (cx, cy),
            align="center",
        )
        if reason:
            reason_text = (
                self.tr(reason) if reason in i18n.all_keys() else reason
            )
            self._text(
                reason_text,
                self.font_m,
                (220, 186, 186),
                (cx, cy + 82),
                align="center",
            )
        level = getattr(world, "level_index", 0) + 1
        remaining = (
            world.remaining_enemies
            if hasattr(world, "remaining_enemies")
            else 0
        )
        self._text(
            self.tr(
                "gameover.reached",
                level=level,
                total=config.LEVEL_COUNT,
            ),
            self.font_s,
            (150, 180, 202),
            (cx, cy + 132),
            align="center",
        )
        self._text(
            self.tr("gameover.remaining", remaining=remaining),
            self.font_s,
            (150, 180, 202),
            (cx, cy + 160),
            align="center",
        )
        self._text(
            self.tr("gameover.retry"),
            self.font_m,
            config.HOLO_WHITE,
            (cx, cy + 220),
            align="center",
        )
        self._text(
            self.tr("gameover.quit"),
            self.font_s,
            (150, 180, 202),
            (cx, cy + 254),
            align="center",
        )

    def draw_victory(self, world) -> None:
        self._dim(182)
        cx = self.width // 2
        cy = 230
        self._begin_glow()
        self._glow_circle(
            config.P1_BLUE, (cx, cy), 260, strength=0.4
        )
        self._glow_circle(
            config.HOLO_WHITE, (cx, cy), 120, strength=0.3
        )
        self._end_glow()
        for index in range(3):
            pygame.draw.circle(
                self.screen,
                _scale(config.HOLO_WHITE, 0.35 - index * 0.08),
                (cx, cy),
                120 + index * 38,
                1,
            )
        self._text(
            self.tr("victory.title"),
            self.font_xl,
            (238, 250, 255),
            (cx, cy),
            align="center",
        )
        self._text(
            self.tr("victory.subtitle"),
            self.font_m,
            config.P2_AMBER,
            (cx, cy + 78),
            align="center",
        )
        shared = getattr(world, "shared_lives", 0)
        self._text(
            self.tr("victory.revives", count=shared),
            self.font_s,
            (150, 200, 226),
            (cx, cy + 126),
            align="center",
        )
        self._text(
            self.tr("victory.epilogue"),
            self.font_s,
            (126, 164, 192),
            (cx, cy + 158),
            align="center",
        )
        self._text(
            self.tr("victory.again"),
            self.font_m,
            config.HOLO_WHITE,
            (cx, cy + 226),
            align="center",
        )

    def draw_intro(self, level_index: int, remaining: float) -> None:
        alpha = int(142 * max(0.0, min(1.0, remaining / 1.2)))
        band = pygame.Rect(0, 238, self.width, 168)
        self._dim_rect(band, alpha)
        cx = self.width // 2
        is_boss = level_index == config.BOSS_LEVEL
        color = _ELITE_MAGENTA if is_boss else config.HOLO_WHITE
        title = (
            self.tr("intro.boss")
            if is_boss
            else self.tr("intro.level", level=level_index + 1)
        )
        self._text(
            title,
            self.font_xl,
            color,
            (cx, 292),
            align="center",
            alpha=alpha,
        )
        self._text(
            self.tr("intro.boss_subtitle")
            if is_boss
            else self.tr("intro.ready"),
            self.font_m,
            config.P2_AMBER if is_boss else config.P1_BLUE,
            (cx, 348),
            align="center",
            alpha=alpha,
        )
        shown_level = max(1, min(config.LEVEL_COUNT, level_index + 1))
        self._text(
            f"{shown_level} / {config.LEVEL_COUNT}",
            self.font_s,
            (150, 180, 202),
            (cx, 382),
            align="center",
            alpha=alpha,
        )
