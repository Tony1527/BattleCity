from __future__ import annotations

import math
from array import array

import pygame

_TONES = {
    "shoot": (960.0, 700.0, 0.07, 0.30, "square"),
    "hit": (360.0, 220.0, 0.09, 0.30, "square"),
    "explosion": (160.0, 50.0, 0.32, 0.40, "sine"),
    "laser": (1600.0, 900.0, 0.14, 0.30, "sine"),
    "pick": (660.0, 990.0, 0.16, 0.30, "sine"),
    "lose": (300.0, 90.0, 0.50, 0.30, "square"),
    "win": (523.0, 1046.0, 0.45, 0.30, "sine"),
}

_PCM_LIMITS = {
    -16: ("h", 32767, 0),
    16: ("H", 65535, 32768),
    -8: ("b", 127, 0),
    8: ("B", 255, 128),
    -32: ("i", 2147483647, 0),
    32: ("I", 4294967295, 2147483648),
}


def _wave_value(phase: float, wave: str) -> float:
    sine = math.sin(phase)
    if wave == "square":
        return 1.0 if sine >= 0.0 else -1.0
    return sine


def _encode_frames(
    start_freq: float,
    end_freq: float,
    duration: float,
    volume: float,
    wave: str,
    sample_rate: int,
    fmt: int,
    channels: int,
) -> bytes:
    typecode, limit, offset = _PCM_LIMITS[fmt]
    count = max(1, int(sample_rate * duration))
    channel_count = max(1, int(channels))
    values = []
    phase = 0.0

    for index in range(count):
        progress = index / count
        frequency = start_freq + (end_freq - start_freq) * progress
        phase += math.tau * frequency / sample_rate
        attack = min(1.0, index / max(1, sample_rate * 0.004))
        release = 1.0 - progress
        value = (
            _wave_value(phase, wave) * volume * attack * release
        )
        sample = int(value * limit) + offset
        for _ in range(channel_count):
            values.append(sample)

    return array(typecode, values).tobytes()


class Audio:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = False
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        if not enabled:
            return

        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init()
            mixer_state = pygame.mixer.get_init()
            if mixer_state is None:
                return
            sample_rate, fmt, channels = mixer_state
            if fmt not in _PCM_LIMITS:
                return
            for name, spec in _TONES.items():
                try:
                    buffer = _encode_frames(
                        *spec, sample_rate, fmt, channels
                    )
                    self._sounds[name] = pygame.mixer.Sound(buffer=buffer)
                except Exception:
                    continue
        except Exception:
            self._sounds = {}
            self.enabled = False
            return

        self.enabled = bool(self._sounds)

    def play(self, name: str) -> None:
        if not self.enabled:
            return
        sound = self._sounds.get(name)
        if sound is None:
            return
        try:
            sound.play()
        except Exception:
            return

    def toggle(self) -> bool:
        if not self._sounds:
            self.enabled = False
            return False
        self.enabled = not self.enabled
        return self.enabled
