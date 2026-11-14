"""Animated birthday card - Gloria Edition (Revamped & Upgraded).

A state-of-the-art interactive animated celebration featuring:
- Hardware-accelerated 60 FPS graphics with smooth alpha blending & glow effects
- Realistic heartbeat pulse and floating hearts & rose petal physics
- Golden-angle spiral roses with anti-aliased botanical curves
- Procedural music-box audio synthesizer playing the "Happy Birthday" melody (pure NumPy/Wave, zero external files needed!)
- Interactive Love Letter modal reading the special letter with particle bursts
- Interactive music toggle with animated equalizer bars
- Particle fireworks on click and magical fairy-dust cursor trail
- Dual-engine architecture: Next-gen Pygame-CE engine (default) + classic Turtle fallback (--engine turtle)

Controls:
    Left Click : Open letter / Toggle music / Spawn heart fireworks
    Space      : Toggle background music
    L          : Open / Close the Love Letter
    F11        : Toggle Fullscreen
    Esc        : Close letter or Exit
"""

from __future__ import annotations

import argparse
import io
import math
import os
import random
import sys
import time
import wave
from dataclasses import dataclass
from functools import lru_cache
from typing import Sequence, Tuple

Point = Tuple[float, float]
ColorRGB = Tuple[int, int, int]
ColorRGBA = Tuple[int, int, int, int]

# ==========================================
# CONFIGURATION & THEME
# ==========================================

DEFAULT_WIDTH = 1040
DEFAULT_HEIGHT = 860
DEFAULT_FPS = 60
DEFAULT_SEED = 7

# Color Palette (Romantic Rose & Midnight Wine)
COLOR_BG_TOP = (18, 13, 36)         # Deep midnight amethyst
COLOR_BG_BOTTOM = (45, 10, 27)      # Rich dark wine
COLOR_HEART_PINK = (255, 71, 126)   # #ff477e
COLOR_HEART_DEEP = (175, 23, 77)    # #af174d
COLOR_HEART_CORE = (255, 107, 154)  # #ff6b9a
COLOR_ROSE_GOLD = (255, 215, 0)
COLOR_TEXT_WHITE = (255, 255, 255)
COLOR_TEXT_CREAM = (255, 244, 246)
COLOR_TEXT_ROSE = (255, 182, 193)
COLOR_TEXT_MUTED = (255, 214, 231)

LOVE_LETTER_TITLE = "My Dearest Gloria…"
LOVE_LETTER_PARAGRAPHS = [
    "I hope today reminds you how precious you are. Your smile, your kindness, "
    "and the person you are make this world a little more beautiful.",

    "I cannot promise that every day will be perfect, but I hope to keep choosing "
    "patience, honesty, laughter, and growth. I hope that, with time, we can build "
    "something genuine: a love that feels safe, a friendship that stays strong, "
    "and memories that become our favourite stories.",

    "May God guide your steps, protect your heart, strengthen you when life gets "
    "difficult, and surprise you with blessings greater than the ones you have "
    "been praying for. Keep dreaming boldly, keep shining, and never forget your worth.",
]
LOVE_LETTER_CLOSING = "Happy birthday, my beautiful future queen. May this year be as lovely as the smile you bring into the world. 🌹❤️"


@dataclass(frozen=True)
class StoryLine:
    text: str
    y_offset: int
    size: int
    color: ColorRGB
    bold: bool
    start: float           # seconds after launch
    duration: float = 1.0  # fade-in duration


STORY_SEQUENCE: tuple[StoryLine, ...] = (
    StoryLine("HAPPY BIRTHDAY", -340, 32, (255, 182, 193), True, 0.4),
    StoryLine("GLORIA URINAVI", -296, 30, (255, 255, 255), True, 1.1),
    StoryLine("MY FUTURE WIFEY", -52, 21, (255, 255, 255), True, 2.0),
    StoryLine("YOU MAKE MY WORLD BRIGHTER", -18, 14, (255, 230, 239), False, 2.6),
    StoryLine("May your day be as beautiful as your heart.", 270, 18, (255, 255, 255), False, 3.4),
    StoryLine("May this new chapter bring you happiness, peace,", 298, 15, (255, 214, 231), False, 4.3),
    StoryLine("answered prayers, endless laughter and beautiful memories.", 324, 15, (255, 214, 231), False, 4.9),
    StoryLine("Never stop shining, Gloria. You deserve the very best.", 350, 15, (255, 255, 255), False, 5.7),
    StoryLine("With love, your future hubby ❤️", 388, 17, (255, 143, 171), True, 6.6),
)


# ==========================================
# MATHEMATICAL HELPERS (Vector & Curve Logic)
# ==========================================

@lru_cache(maxsize=1)
def get_unit_heart_curve(step: int = 2) -> tuple[Point, ...]:
    """Generates normalized mathematical heart coordinates centered at (0, 0)."""
    pts: list[Point] = []
    for deg in range(0, 360, step):
        a = math.radians(deg)
        x = 16 * math.sin(a) ** 3
        y = -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a))
        pts.append((x, y))
    return tuple(pts)


def heartbeat_pulse(t: float, period: float = 1.25) -> float:
    """Anatomical 'lub-dub' double-systole heartbeat waveform in [0, ~1.6]."""
    lub = max(0.0, math.sin(math.tau * (t / period))) ** 6
    dub = max(0.0, math.sin(math.tau * (t / period - 0.18))) ** 6
    return lub + 0.6 * dub


def clamp(val: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, val))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp_color(c1: ColorRGB, c2: ColorRGB, t: float) -> ColorRGB:
    t = clamp(t)
    return (
        round(c1[0] + (c2[0] - c1[0]) * t),
        round(c1[1] + (c2[1] - c1[1]) * t),
        round(c1[2] + (c2[2] - c1[2]) * t),
    )


def ease_out_back(x: float, c1: float = 1.70158) -> float:
    c3 = c1 + 1
    return 1 + c3 * ((x - 1) ** 3) + c1 * ((x - 1) ** 2)


def ease_out_cubic(x: float) -> float:
    return 1 - (1 - x) ** 3


# ==========================================
# PROCEDURAL AUDIO SYNTHESIZER
# ==========================================

class AudioEngine:
    """Procedurally synthesizes music-box tones & chimes with zero external sound files."""

    def __init__(self, sample_rate: int = 44100) -> None:
        self.sample_rate = sample_rate
        self.enabled = False
        self.is_playing = False
        self.birthday_sound = None
        self.chime_sound = None

        try:
            import pygame
            # Safe initialization
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=sample_rate, size=-16, channels=2, buffer=1024)
            self.enabled = True
            self._build_sounds()
        except Exception:
            # Headless or missing audio device: app continues gracefully without sound
            self.enabled = False

    def _build_sounds(self) -> None:
        try:
            import numpy as np
            import pygame

            # 1. Synthesize "Happy Birthday" melody (music box / celesta timbre)
            tune = [
                (67, 0.75), (67, 0.25), (69, 1.0), (67, 1.0), (72, 1.0), (71, 2.0),
                (67, 0.75), (67, 0.25), (69, 1.0), (67, 1.0), (74, 1.0), (72, 2.0),
                (67, 0.75), (67, 0.25), (79, 1.0), (76, 1.0), (72, 1.0), (71, 1.0), (69, 2.0),
                (77, 0.75), (77, 0.25), (76, 1.0), (72, 1.0), (74, 1.0), (72, 3.0),
            ]
            beat_sec = 0.54
            total_beats = sum(b for _, b in tune) + 1.2
            total_samples = int(total_beats * beat_sec * self.sample_rate)
            full_audio = np.zeros(total_samples, dtype=np.float32)

            curr = int(0.15 * self.sample_rate)
            for midi_note, beats in tune:
                freq = 440.0 * (2.0 ** ((midi_note - 69) / 12.0))
                dur = beats * beat_sec
                tail = 0.45
                n_samples = int((dur + tail) * self.sample_rate)
                t = np.linspace(0, dur + tail, n_samples, False)

                # Celesta bell envelope + harmonic warmth
                env = np.exp(-t * 3.2) * (1.0 - np.exp(-t * 90.0))
                bell = (
                    0.56 * np.sin(2 * np.pi * freq * t)
                    + 0.26 * np.sin(2 * np.pi * freq * 2.0 * t) * np.exp(-t * 1.5)
                    + 0.12 * np.sin(2 * np.pi * freq * 3.0 * t) * np.exp(-t * 2.8)
                    + 0.06 * np.sin(2 * np.pi * freq * 4.2 * t) * np.exp(-t * 4.2)
                )
                note_audio = bell * env * 0.42
                end_s = min(curr + n_samples, total_samples)
                actual_len = end_s - curr
                full_audio[curr:end_s] += note_audio[:actual_len]
                curr += int(dur * self.sample_rate)

            # Normalize & export to in-memory stereo wav
            mx = np.max(np.abs(full_audio))
            if mx > 0:
                full_audio = (full_audio / mx) * 0.72

            audio_int16 = (full_audio * 32767).astype(np.int16)
            stereo = np.column_stack((audio_int16, audio_int16))

            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(stereo.tobytes())
            buf.seek(0)
            self.birthday_sound = pygame.mixer.Sound(buf)
            self.birthday_sound.set_volume(0.65)

            # 2. Synthesize magical sparkle chime for clicks & letter opening
            c_dur = 0.55
            ct = np.linspace(0, c_dur, int(c_dur * self.sample_rate), False)
            chime = (
                0.35 * np.sin(2 * np.pi * 1046.50 * ct) * np.exp(-5.5 * ct)  # C6
                + 0.30 * np.sin(2 * np.pi * 1318.51 * ct) * np.exp(-6.5 * ct)  # E6
                + 0.25 * np.sin(2 * np.pi * 1567.98 * ct) * np.exp(-7.5 * ct)  # G6
                + 0.15 * np.sin(2 * np.pi * 2093.00 * ct) * np.exp(-9.0 * ct)  # C7
            )
            c_mx = np.max(np.abs(chime))
            if c_mx > 0:
                chime = (chime / c_mx) * 0.75
            c_int16 = (chime * 32767).astype(np.int16)
            c_stereo = np.column_stack((c_int16, c_int16))

            c_buf = io.BytesIO()
            with wave.open(c_buf, "wb") as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(c_stereo.tobytes())
            c_buf.seek(0)
            self.chime_sound = pygame.mixer.Sound(c_buf)
            self.chime_sound.set_volume(0.7)

        except Exception:
            self.enabled = False

    def play_music(self) -> None:
        if not self.enabled:
            return
        # If user has an assets/birthday-song.mp3, prioritize it
        for path in ("assets/birthday-song.mp3", "birthday-song.mp3"):
            if os.path.exists(path):
                try:
                    import pygame
                    pygame.mixer.music.load(path)
                    pygame.mixer.music.play(-1)
                    pygame.mixer.music.set_volume(0.7)
                    self.is_playing = True
                    return
                except Exception:
                    pass
        # Fall back to procedural musicbox
        if self.birthday_sound:
            self.birthday_sound.play(loops=-1)
            self.is_playing = True

    def pause_music(self) -> None:
        if not self.enabled:
            return
        import pygame
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()
        if self.birthday_sound:
            self.birthday_sound.stop()
        self.is_playing = False

    def toggle_music(self) -> None:
        if self.is_playing:
            self.pause_music()
        else:
            self.play_music()

    def play_chime(self) -> None:
        if self.enabled and self.chime_sound:
            self.chime_sound.play()


# ==========================================
# NEXT-GEN PYGAME ENGINE
# ==========================================

class PygameBirthdayCard:
    """High-performance hardware-accelerated animated birthday card for Gloria."""

    def __init__(self, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT,
                 fps: int = DEFAULT_FPS, seed: int = DEFAULT_SEED,
                 fullscreen: bool = False, mute: bool = False,
                 max_frames: int | None = None) -> None:
        import pygame
        self.pygame = pygame

        self.width = width
        self.height = height
        self.fps = fps
        self.max_frames = max_frames
        self.rng = random.Random(seed)
        self.clock = 0.0
        self.frame_count = 0
        self.is_running = False

        # Initialize Pygame Display
        pygame.init()
        pygame.font.init()

        flags = pygame.DOUBLEBUF | pygame.RESIZABLE
        if fullscreen:
            flags |= pygame.FULLSCREEN
        self.screen = pygame.display.set_mode((width, height), flags)
        pygame.display.set_caption("Happy Birthday, My Future Wifey - Gloria! ❤️")

        # Fonts (with graceful fallbacks)
        self._init_fonts()

        # Audio
        self.audio = AudioEngine()
        if not mute:
            self.audio.play_music()

        # Particles & Scene Objects
        self.stars = self._scatter_stars(110)
        self.floaters = [self._spawn_floater(anywhere=True) for _ in range(24)]
        self.burst_particles: list[dict] = []
        self.cursor_trail: list[dict] = []

        # UI State
        self.letter_open = False
        self.letter_anim = 0.0          # 0.0 = closed, 1.0 = open
        self.hover_letter_btn = False
        self.hover_music_btn = False
        self.hover_close_btn = False

        # Pre-rendered Assets & Buffers
        self.bg_surface = self._create_gradient_background()
        self.left_rose_surface = self._render_rose(size=1.18, flip=False)
        self.right_rose_surface = self._render_rose(size=1.18, flip=True)

    def _init_fonts(self) -> None:
        pygame = self.pygame
        # Try romantic cursive fonts available on Windows/Mac/Linux
        cursive_names = ["gabriola", "greatvibes", "edwardianscriptitc", "monotypecorsiva", "segoeui"]
        serif_names = ["georgia", "playfairdisplay", "timesnewroman", "palatino"]
        sans_names = ["segoeui", "dmsans", "arial", "helvetica", "calibri"]

        self.font_cursive = self._pick_font(cursive_names, 42)
        self.font_cursive_large = self._pick_font(cursive_names, 62)
        self.font_title = self._pick_font(sans_names, 30, bold=True)
        self.font_name = self._pick_font(sans_names, 28, bold=True)
        self.font_serif = self._pick_font(serif_names, 18)
        self.font_body = self._pick_font(sans_names, 15)
        self.font_body_bold = self._pick_font(sans_names, 15, bold=True)
        self.font_small = self._pick_font(sans_names, 13)
        self.font_script_sig = self._pick_font(cursive_names, 34)

    def _pick_font(self, candidates: list[str], size: int, bold: bool = False):
        pygame = self.pygame
        for name in candidates:
            match = pygame.font.match_font(name)
            if match:
                try:
                    f = pygame.font.Font(match, size)
                    f.set_bold(bold)
                    return f
                except Exception:
                    continue
        f = pygame.font.Font(None, size)
        f.set_bold(bold)
        return f

    def _create_gradient_background(self):
        pygame = self.pygame
        surf = pygame.Surface((self.width, self.height))
        # Smooth vertical wine gradient
        for y in range(self.height):
            t = y / max(1, self.height)
            color = lerp_color(COLOR_BG_TOP, COLOR_BG_BOTTOM, t)
            pygame.draw.line(surf, color, (0, y), (self.width, y))

        # Add warm radial ambient glow at the center
        glow_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        cx, cy = self.width // 2, int(self.height * 0.44)
        max_r = int(min(self.width, self.height) * 0.52)
        for r in range(max_r, 0, -6):
            factor = (1.0 - r / max_r) ** 1.8
            alpha = int(45 * factor)
            pygame.draw.circle(glow_surf, (220, 38, 98, alpha), (cx, cy), r)
        surf.blit(glow_surf, (0, 0))
        return surf

    def _scatter_stars(self, n: int) -> list[dict]:
        stars = []
        for _ in range(n):
            stars.append({
                "x": self.rng.randint(10, self.width - 10),
                "y": self.rng.randint(10, self.height - 10),
                "size": self.rng.choice([1.5, 2.0, 2.5, 3.2]),
                "phase": self.rng.uniform(0, math.tau),
                "speed": self.rng.uniform(1.2, 3.5),
                "color": self.rng.choice([(255, 240, 245), (255, 214, 231), (255, 255, 200)]),
            })
        return stars

    def _spawn_floater(self, anywhere: bool = False) -> dict:
        palette = [
            (255, 71, 126, 210),   # Pink
            (255, 143, 171, 200),  # Rose
            (255, 182, 193, 190),  # Soft peach
            (201, 24, 74, 220),    # Ruby
        ]
        return {
            "x": self.rng.uniform(40, self.width - 40),
            "y": self.rng.uniform(30, self.height - 30) if anywhere else self.height + self.rng.uniform(10, 60),
            "speed": self.rng.uniform(32, 68),
            "scale": self.rng.uniform(0.7, 1.4),
            "amp": self.rng.uniform(12, 32),
            "freq": self.rng.uniform(0.8, 1.8),
            "phase": self.rng.uniform(0, math.tau),
            "color": self.rng.choice(palette),
            "rot": self.rng.uniform(-30, 30),
            "rot_speed": self.rng.uniform(-20, 20),
        }

    def _spawn_burst(self, x: float, y: float, count: int = 24) -> None:
        """Spawns an explosion of hearts and sparkling gold dust on click."""
        for _ in range(count):
            angle = self.rng.uniform(0, math.tau)
            speed = self.rng.uniform(70, 260)
            self.burst_particles.append({
                "x": x,
                "y": y,
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed - self.rng.uniform(20, 60),
                "scale": self.rng.uniform(0.6, 1.3),
                "life": 1.0,
                "decay": self.rng.uniform(0.7, 1.4),
                "color": self.rng.choice([
                    (255, 71, 126), (255, 182, 193), (255, 215, 0), (255, 255, 255)
                ]),
                "type": self.rng.choice(["heart", "sparkle", "star"]),
            })

    def _render_rose(self, size: float = 1.0, flip: bool = False):
        """Draws an artistic golden-angle spiral rose with stem & leaves."""
        pygame = self.pygame
        w, h = int(180 * size), int(260 * size)
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, int(70 * size)

        # Curved Stem
        stem_pts = [
            (cx, cy),
            (cx + (10 if not flip else -10), cy + int(70 * size)),
            (cx, cy + int(150 * size)),
        ]
        pygame.draw.lines(surf, (34, 139, 34), False, stem_pts, max(2, int(5 * size)))

        # Leaves
        def draw_leaf(lx, ly, length, angle_deg):
            rad = math.radians(angle_deg)
            cos_a, sin_a = math.cos(rad), math.sin(rad)
            steps = 10
            pts = []
            for s in range(steps + 1):
                px = (s / steps) * length
                py = math.sin(math.pi * s / steps) * length * 0.32
                pts.append((lx + px * cos_a - py * sin_a, ly + px * sin_a + py * cos_a))
            for s in range(steps, -1, -1):
                px = (s / steps) * length
                py = -math.sin(math.pi * s / steps) * length * 0.32
                pts.append((lx + px * cos_a - py * sin_a, ly + px * sin_a + py * cos_a))
            if len(pts) > 2:
                pygame.draw.polygon(surf, (50, 205, 114), pts)
                pygame.draw.polygon(surf, (20, 83, 45), pts, 1)

        draw_leaf(cx + (2 if not flip else -2), cy + int(60 * size), 38 * size, 145 if not flip else 35)
        draw_leaf(cx - (2 if not flip else -2), cy + int(95 * size), 34 * size, 30 if not flip else 150)

        # Petals via Fibonacci Golden Angle (137.5 deg)
        petals = 28
        for i in range(petals):
            f = i / (petals - 1)
            ang = math.radians(i * 137.5)
            r = (1.0 - f) * 18.0 * size
            px = cx + math.cos(ang) * r
            py = cy + math.sin(ang) * r
            p_radius = max(2, int((26 - 15 * f) * size * 0.5))
            p_color = lerp_color((122, 12, 46), (255, 143, 163), f)
            pygame.draw.circle(surf, p_color, (int(px), int(py)), p_radius)

        pygame.draw.circle(surf, (255, 208, 218), (cx, cy), max(2, int(4 * size)))
        if flip:
            surf = pygame.transform.flip(surf, True, False)
        return surf

    def _draw_heart_polygon(self, surface, cx: float, cy: float, scale: float,
                            fill_color: ColorRGBA, outline_color: ColorRGBA | None = None,
                            outline_width: int = 1):
        """Draws an anti-aliased scaled heart shape with alpha fill."""
        pygame = self.pygame
        curve = get_unit_heart_curve()
        pts = [(int(cx + x * scale), int(cy + y * scale)) for x, y in curve]
        if len(pts) > 2:
            pygame.draw.polygon(surface, fill_color, pts)
            if outline_color and outline_width > 0:
                pygame.draw.polygon(surface, outline_color, pts, outline_width)

    def _draw_sparkle(self, surface, cx: float, cy: float, size: float, color: ColorRGBA):
        pygame = self.pygame
        s = size
        pts = [
            (cx, cy - s), (cx + s * 0.28, cy - s * 0.28),
            (cx + s, cy), (cx + s * 0.28, cy + s * 0.28),
            (cx, cy + s), (cx - s * 0.28, cy + s * 0.28),
            (cx - s, cy), (cx - s * 0.28, cy - s * 0.28),
        ]
        pygame.draw.polygon(surface, color, [(int(px), int(py)) for px, py in pts])

    # ---- MAIN LOOP -------------------------------------------------

    def run(self) -> None:
        pygame = self.pygame
        clock = pygame.time.Clock()
        self.is_running = True
        last_time = time.perf_counter()

        while self.is_running:
            now = time.perf_counter()
            dt = min(now - last_time, 0.1)
            last_time = now
            self.clock += dt
            self.frame_count += 1

            # Event Handling
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.is_running = False
                elif event.type == pygame.VIDEORESIZE:
                    self.width, self.height = event.w, event.h
                    self.screen = pygame.display.set_mode((self.width, self.height), pygame.DOUBLEBUF | pygame.RESIZABLE)
                    self.bg_surface = self._create_gradient_background()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self.letter_open:
                            self.letter_open = False
                        else:
                            self.is_running = False
                    elif event.key == pygame.K_SPACE:
                        self.audio.toggle_music()
                    elif event.key == pygame.K_l:
                        self.letter_open = not self.letter_open
                        if self.letter_open:
                            self.audio.play_chime()
                            self._spawn_burst(self.width // 2, self.height // 2, 32)
                    elif event.key == pygame.K_F11:
                        pygame.display.toggle_fullscreen()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._handle_click(event.pos)
                elif event.type == pygame.MOUSEMOTION:
                    self._handle_motion(event.pos)

            # Update Animations
            self._update(dt)

            # Render Scene
            self._render()
            pygame.display.flip()

            # Testing frame cap
            if self.max_frames is not None and self.frame_count >= self.max_frames:
                self.is_running = False

            clock.tick(self.fps)

        pygame.quit()

    def _handle_motion(self, pos: tuple[int, int]) -> None:
        mx, my = pos
        # Fairy-dust trail on cursor movement
        if self.rng.random() < 0.4:
            self.cursor_trail.append({
                "x": mx + self.rng.uniform(-4, 4),
                "y": my + self.rng.uniform(-4, 4),
                "life": 1.0,
                "decay": self.rng.uniform(1.8, 3.2),
                "size": self.rng.uniform(2.0, 4.5),
                "color": self.rng.choice([(255, 182, 193), (255, 215, 0), (255, 255, 255)]),
            })

    def _handle_click(self, pos: tuple[int, int]) -> None:
        mx, my = pos

        # 1. Close Button inside Love Letter Modal
        if self.letter_open:
            # Letter modal bounds
            m_w = min(680, self.width - 60)
            m_h = min(560, self.height - 80)
            m_x = (self.width - m_w) // 2
            m_y = (self.height - m_h) // 2
            close_rect = self.pygame.Rect(m_x + m_w - 46, m_y + 14, 34, 34)
            if close_rect.collidepoint(pos):
                self.letter_open = False
                self.audio.play_chime()
                return

            # Click outside modal closes it
            modal_rect = self.pygame.Rect(m_x, m_y, m_w, m_h)
            if not modal_rect.collidepoint(pos):
                self.letter_open = False
                return

        # 2. Check "Open Love Letter" Button
        btn_w, btn_h = 240, 46
        btn_x = (self.width - btn_w) // 2
        btn_y = int(self.height * 0.76)
        letter_btn_rect = self.pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        if letter_btn_rect.collidepoint(pos) and not self.letter_open:
            self.letter_open = True
            self.audio.play_chime()
            self._spawn_burst(btn_x + btn_w // 2, btn_y + btn_h // 2, 36)
            return

        # 3. Check Music Toggle Button (bottom right)
        music_w, music_h = 135, 38
        music_x = self.width - music_w - 20
        music_y = self.height - music_h - 20
        music_btn_rect = self.pygame.Rect(music_x, music_y, music_w, music_h)
        if music_btn_rect.collidepoint(pos):
            self.audio.toggle_music()
            return

        # 4. Clicking anywhere else spawns hearts & sparkles!
        self.audio.play_chime()
        self._spawn_burst(mx, my, 22)

    def _update(self, dt: float) -> None:
        # Love Letter Modal Animation Easing
        target_anim = 1.0 if self.letter_open else 0.0
        anim_speed = 4.2
        if self.letter_anim < target_anim:
            self.letter_anim = min(target_anim, self.letter_anim + anim_speed * dt)
        elif self.letter_anim > target_anim:
            self.letter_anim = max(target_anim, self.letter_anim - anim_speed * dt)

        # Update Floating Hearts
        for f in self.floaters:
            f["y"] -= f["speed"] * dt
            f["rot"] += f["rot_speed"] * dt
            if f["y"] < -40:
                f.update(self._spawn_floater(anywhere=False))

        # Update Click Burst Particles
        alive_burst = []
        for p in self.burst_particles:
            p["life"] -= p["decay"] * dt
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] += 120.0 * dt  # gentle gravity
            p["vx"] *= 0.98        # air drag
            if p["life"] > 0:
                alive_burst.append(p)
        self.burst_particles = alive_burst

        # Update Cursor Fairy Dust
        alive_trail = []
        for c in self.cursor_trail:
            c["life"] -= c["decay"] * dt
            c["y"] -= 15.0 * dt
            if c["life"] > 0:
                alive_trail.append(c)
        self.cursor_trail = alive_trail

    def _render(self) -> None:
        pygame = self.pygame
        # 1. Background Gradient
        self.screen.blit(self.bg_surface, (0, 0))

        # 2. Twinkling Background Stars
        self._draw_stars()

        # 3. Flanking Golden Roses
        rose_y = int(self.height * 0.46)
        self.screen.blit(self.left_rose_surface, (int(self.width * 0.06), rose_y))
        self.screen.blit(self.right_rose_surface, (int(self.width * 0.94 - self.right_rose_surface.get_width()), rose_y))

        # 4. Floating Hearts & Rose Petals
        self._draw_floaters()

        # 5. Center Beating Heart
        self._draw_main_heart()

        # 6. Sparkle Accents
        self._draw_sparkles()

        # 7. Story Texts
        self._draw_story_texts()

        # 8. Interactive "Open Love Letter" Button
        self._draw_letter_button()

        # 9. Interactive Music Equalizer Button
        self._draw_music_button()

        # 10. Click Burst Particles & Cursor Trail
        self._draw_particles()

        # 11. Modal Love Letter Overlay (if active)
        if self.letter_anim > 0.01:
            self._draw_love_letter_modal()

    def _draw_stars(self) -> None:
        pygame = self.pygame
        for s in self.stars:
            twinkle = 0.5 + 0.5 * math.sin(self.clock * s["speed"] + s["phase"])
            alpha = int(clamp(0.25 + 0.75 * twinkle) * 255)
            r, g, b = s["color"]
            star_surf = pygame.Surface((12, 12), pygame.SRCALPHA)
            pygame.draw.circle(star_surf, (r, g, b, alpha), (6, 6), max(1, int(s["size"] * twinkle)))
            self.screen.blit(star_surf, (s["x"] - 6, s["y"] - 6))

    def _draw_floaters(self) -> None:
        pygame = self.pygame
        floater_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        for f in self.floaters:
            x = f["x"] + math.sin(self.clock * f["freq"] + f["phase"]) * f["amp"]
            y = f["y"]
            r, g, b, a = f["color"]
            # Soft fade near top
            if y < 140:
                a = int(a * max(0.0, y / 140.0))
            self._draw_heart_polygon(floater_surf, x, y, f["scale"] * 0.85, (r, g, b, a))
        self.screen.blit(floater_surf, (0, 0))

    def _draw_main_heart(self) -> None:
        pygame = self.pygame
        cx = self.width // 2
        cy = int(self.height * 0.44)

        # Pulse formula
        k = 1.0 + 0.065 * heartbeat_pulse(self.clock)

        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)

        # Glowing Multi-Ring Outer Aura
        for ring_idx, (r_scale, r_alpha) in enumerate([(15.8, 28), (14.6, 55), (13.5, 90)]):
            self._draw_heart_polygon(overlay, cx, cy, r_scale * k, (255, 71, 126, r_alpha))

        # Deep Heart Body
        self._draw_heart_polygon(overlay, cx, cy, 12.8 * k, (175, 23, 77, 245), (255, 182, 193, 220), 2)

        # Bright Inner Heart
        self._draw_heart_polygon(overlay, cx, cy, 11.4 * k, (255, 71, 126, 255), (255, 200, 215, 240), 2)

        # Specular Curved Highlight
        self._draw_heart_polygon(overlay, cx, cy - 4 * k, 8.2 * k, (255, 107, 154, 210))

        self.screen.blit(overlay, (0, 0))

    def _draw_sparkles(self) -> None:
        pygame = self.pygame
        sparkle_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        cx = self.width // 2
        cy = int(self.height * 0.44)

        positions = [
            (cx - 240, cy - 120, 11),
            (cx + 240, cy - 120, 11),
            (cx - 220, cy + 130, 9),
            (cx + 220, cy + 130, 9),
            (cx - 150, cy - 230, 8),
            (cx + 150, cy - 230, 8),
        ]
        for sx, sy, size in positions:
            twinkle = 0.5 + 0.5 * abs(math.sin(self.clock * 2.2 + sx))
            self._draw_sparkle(sparkle_surf, sx, sy, size * twinkle, (255, 240, 245, int(220 * twinkle)))
        self.screen.blit(sparkle_surf, (0, 0))

    def _draw_story_texts(self) -> None:
        pygame = self.pygame
        cx = self.width // 2
        cy = int(self.height * 0.44)

        for line in STORY_SEQUENCE:
            elapsed = self.clock - line.start
            if elapsed <= 0:
                continue
            alpha = clamp(elapsed / line.duration)

            font = self.font_body
            if line.size >= 30:
                font = self.font_title if line.text.isupper() else self.font_cursive_large
            elif line.size >= 24:
                font = self.font_name
            elif line.size >= 17:
                font = self.font_serif

            r, g, b = line.color
            txt_surf = font.render(line.text, True, (r, g, b))
            txt_surf.set_alpha(int(alpha * 255))
            rect = txt_surf.get_rect(center=(cx, cy + line.y_offset))
            self.screen.blit(txt_surf, rect)

    def _draw_letter_button(self) -> None:
        """Draws the romantic 'Open Love Letter' pill button."""
        pygame = self.pygame
        btn_w, btn_h = 246, 46
        btn_x = (self.width - btn_w) // 2
        btn_y = int(self.height * 0.76)

        m_pos = pygame.mouse.get_pos()
        hover = pygame.Rect(btn_x, btn_y, btn_w, btn_h).collidepoint(m_pos)

        # Breathing scale
        pulse = 1.0 + 0.03 * math.sin(self.clock * 3.0) if hover else 1.0
        w, h = int(btn_w * pulse), int(btn_h * pulse)
        x = btn_x - (w - btn_w) // 2
        y = btn_y - (h - btn_h) // 2

        btn_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        # Background gradient pill
        bg_col = (201, 41, 104, 235) if hover else (141, 23, 77, 215)
        pygame.draw.rect(btn_surf, bg_col, (0, 0, w, h), border_radius=23)
        pygame.draw.rect(btn_surf, (255, 202, 220, 240), (0, 0, w, h), 2, border_radius=23)

        label = "💌 Open Love Letter" if not self.letter_open else "💌 Letter is Open"
        txt = self.font_body_bold.render(label, True, (255, 255, 255))
        btn_surf.blit(txt, txt.get_rect(center=(w // 2, h // 2)))

        self.screen.blit(btn_surf, (x, y))

    def _draw_music_button(self) -> None:
        """Equalizer music toggle button in bottom-right corner."""
        pygame = self.pygame
        w, h = 135, 38
        x = self.width - w - 20
        y = self.height - h - 20

        m_pos = pygame.mouse.get_pos()
        hover = pygame.Rect(x, y, w, h).collidepoint(m_pos)

        btn_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        bg_col = (48, 13, 32, 230) if hover else (36, 10, 24, 190)
        pygame.draw.rect(btn_surf, bg_col, (0, 0, w, h), border_radius=19)
        pygame.draw.rect(btn_surf, (255, 182, 193, 160), (0, 0, w, h), 1, border_radius=19)

        # Equalizer bouncing bars
        bar_x = 18
        for i in range(3):
            bar_h = 4
            if self.audio.is_playing:
                bar_h = int(5 + 9 * abs(math.sin(self.clock * 5.0 + i * 1.1)))
            bx = bar_x + i * 5
            by = h // 2 + 5 - bar_h
            pygame.draw.rect(btn_surf, (255, 107, 154), (bx, by, 3, bar_h), border_radius=1)

        status_text = "Pause" if self.audio.is_playing else "Play Music"
        txt = self.font_small.render(status_text, True, COLOR_TEXT_CREAM)
        btn_surf.blit(txt, (bar_x + 20, (h - txt.get_height()) // 2))

        self.screen.blit(btn_surf, (x, y))

    def _draw_particles(self) -> None:
        pygame = self.pygame
        surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)

        # Click burst particles
        for p in self.burst_particles:
            alpha = int(clamp(p["life"]) * 255)
            r, g, b = p["color"]
            if p["type"] == "heart":
                self._draw_heart_polygon(surf, p["x"], p["y"], p["scale"] * 0.7, (r, g, b, alpha))
            else:
                self._draw_sparkle(surf, p["x"], p["y"], p["scale"] * 5.0, (r, g, b, alpha))

        # Cursor trail
        for c in self.cursor_trail:
            alpha = int(clamp(c["life"]) * 200)
            r, g, b = c["color"]
            pygame.draw.circle(surf, (r, g, b, alpha), (int(c["x"]), int(c["y"])), max(1, int(c["size"])))

        self.screen.blit(surf, (0, 0))

    def _draw_love_letter_modal(self) -> None:
        """Displays the heartfelt birthday love letter inside a frosted glass modal."""
        pygame = self.pygame
        ease = ease_out_back(self.letter_anim)

        m_w = min(680, self.width - 60)
        m_h = min(560, self.height - 80)
        target_y = (self.height - m_h) // 2
        # Smooth slide-in from bottom
        current_y = int(self.height - (self.height - target_y) * ease)
        m_x = (self.width - m_w) // 2

        # Dimmed backdrop
        dim_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        dim_surf.fill((0, 0, 0, int(150 * clamp(self.letter_anim))))
        self.screen.blit(dim_surf, (0, 0))

        # Parchment / Frosted glass modal surface
        card = pygame.Surface((m_w, m_h), pygame.SRCALPHA)
        # Deep rich wine background
        pygame.draw.rect(card, (42, 8, 24, 245), (0, 0, m_w, m_h), border_radius=24)
        # Gold & Rose double border
        pygame.draw.rect(card, (255, 179, 207, 210), (0, 0, m_w, m_h), 2, border_radius=24)
        pygame.draw.rect(card, (255, 215, 0, 90), (6, 6, m_w - 12, m_h - 12), 1, border_radius=18)

        # Close '✕' Button
        close_x, close_y = m_w - 42, 16
        m_pos = pygame.mouse.get_pos()
        close_hover = pygame.Rect(m_x + close_x - 4, current_y + close_y - 4, 30, 30).collidepoint(m_pos)
        close_col = (255, 71, 126) if close_hover else (255, 200, 215)
        close_txt = self.font_body_bold.render("✕", True, close_col)
        card.blit(close_txt, (close_x, close_y))

        # Title: "My Dearest Gloria…"
        title_surf = self.font_script_sig.render(LOVE_LETTER_TITLE, True, (255, 159, 194))
        card.blit(title_surf, title_surf.get_rect(center=(m_w // 2, 48)))

        # Decorative ornament line
        pygame.draw.line(card, (255, 157, 190, 160), (m_w // 2 - 80, 78), (m_w // 2 + 80, 78), 1)

        # Word-wrapped paragraphs
        curr_y = 96
        padding_x = 42
        max_text_w = m_w - padding_x * 2

        for p_idx, text in enumerate(LOVE_LETTER_PARAGRAPHS):
            words = text.split(" ")
            line_words: list[str] = []
            for w in words:
                test_line = " ".join(line_words + [w])
                if self.font_body.size(test_line)[0] <= max_text_w:
                    line_words.append(w)
                else:
                    line_surf = self.font_body.render(" ".join(line_words), True, (249, 230, 237))
                    card.blit(line_surf, (padding_x, curr_y))
                    curr_y += self.font_body.get_linesize() + 3
                    line_words = [w]
            if line_words:
                line_surf = self.font_body.render(" ".join(line_words), True, (249, 230, 237))
                card.blit(line_surf, (padding_x, curr_y))
                curr_y += self.font_body.get_linesize() + 3
            curr_y += 12

        # Closing line
        curr_y += 6
        closing_words = LOVE_LETTER_CLOSING.split(" ")
        line_words = []
        for w in closing_words:
            test_line = " ".join(line_words + [w])
            if self.font_body_bold.size(test_line)[0] <= max_text_w:
                line_words.append(w)
            else:
                line_surf = self.font_body_bold.render(" ".join(line_words), True, (255, 192, 213))
                card.blit(line_surf, line_surf.get_rect(center=(m_w // 2, curr_y)))
                curr_y += self.font_body_bold.get_linesize() + 3
                line_words = [w]
        if line_words:
            line_surf = self.font_body_bold.render(" ".join(line_words), True, (255, 192, 213))
            card.blit(line_surf, line_surf.get_rect(center=(m_w // 2, curr_y)))

        self.screen.blit(card, (m_x, current_y))


# ==========================================
# CLASSIC TURTLE FALLBACK ENGINE
# ==========================================

def run_turtle_engine(seed: int = DEFAULT_SEED, fps: int = 30, max_frames: int | None = None) -> None:
    """Preserved classic Turtle graphics engine for minimal standard-library-only execution."""
    import tkinter
    import turtle

    WIDTH, HEIGHT = 1000, 850
    BG = "#120d24"
    HEART_PINK = "#ff477e"

    def hex_to_rgb(color: str) -> tuple[int, int, int]:
        c = color.lstrip("#")
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)

    def mix(c1: str, c2: str, t: float) -> str:
        t = clamp(t)
        a, b = hex_to_rgb(c1), hex_to_rgb(c2)
        return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))

    screen = turtle.Screen()
    screen.setup(width=WIDTH, height=HEIGHT)
    screen.title("Happy Birthday, My Future Wifey - Gloria! (Turtle Mode)")
    screen.bgcolor(BG)
    screen.tracer(0)

    pen = turtle.Turtle()
    pen.hideturtle()
    pen.speed(0)
    pen.penup()

    rng = random.Random(seed)
    running = True

    def close():
        nonlocal running
        running = False
        try:
            screen.bye()
        except Exception:
            pass

    screen.onscreenclick(lambda *_: close())
    screen.onkey(close, "Escape")
    screen.listen()

    start_time = time.perf_counter()
    frames = 0
    curve = get_unit_heart_curve(3)

    while running:
        t = time.perf_counter() - start_time
        pen.clear()

        # Center Heart
        k = 1.0 + 0.05 * heartbeat_pulse(t)
        pts = [(x * 13.0 * k, -y * 13.0 * k) for x, y in curve]
        pen.goto(pts[0])
        pen.color("#ffb6c1", HEART_PINK)
        pen.pendown()
        pen.begin_fill()
        for p in pts[1:]:
            pen.goto(p)
        pen.end_fill()
        pen.penup()

        # Story texts
        for line in STORY_SEQUENCE:
            alpha = clamp((t - line.start) / line.duration)
            if alpha > 0:
                pen.goto(0, -line.y_offset)
                r, g, b = line.color
                pen.color(mix(BG, "#%02x%02x%02x" % (r, g, b), alpha))
                pen.write(line.text, align="center", font=("Arial", line.size, "bold" if line.bold else "normal"))

        screen.update()
        frames += 1
        if max_frames and frames >= max_frames:
            break
        time.sleep(1.0 / fps)

    close()


# ==========================================
# CLI ENTRY POINT
# ==========================================

def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Animated birthday card for Gloria.")
    parser.add_argument("--fps", type=int, default=DEFAULT_FPS, help="Target framerate (default 60)")
    parser.add_argument("--engine", choices=["pygame", "turtle"], default="pygame",
                        help="Render engine: 'pygame' (modern interactive) or 'turtle' (vintage fallback)")
    parser.add_argument("--mute", action="store_true", help="Start with background music paused")
    parser.add_argument("--fullscreen", action="store_true", help="Launch in fullscreen mode")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Random seed for stars/hearts layout")
    parser.add_argument("--frames", type=int, default=None, help="Exit after N frames (for testing)")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH, help="Window width (default 1040)")
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT, help="Window height (default 860)")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)

    if args.engine == "turtle":
        run_turtle_engine(seed=args.seed, fps=min(args.fps, 40), max_frames=args.frames)
    else:
        try:
            import pygame
            PygameBirthdayCard(
                width=args.width,
                height=args.height,
                fps=args.fps,
                seed=args.seed,
                fullscreen=args.fullscreen,
                mute=args.mute,
                max_frames=args.frames,
            ).run()
        except ImportError:
            print("[Warning] pygame-ce not installed, falling back to vintage Turtle engine...")
            run_turtle_engine(seed=args.seed, fps=30, max_frames=args.frames)


if __name__ == "__main__":
    main()
