# 🌹 Happy Birthday, Gloria! (Revamped Python Edition)

An interactive, hardware-accelerated animated birthday celebration written in Python.

---

## ✨ Features & Upgrades

- **Hardware-Accelerated 60 FPS Graphics**: Smooth alpha blending, deep midnight & wine gradient background with warm radial ambient glow.
- **Anatomical Heartbeat Pulse**: Mathematical "lub-dub" double-systole pulsation with glowing multi-tier outer rings and specular highlights.
- **Procedural Music-Box Audio Synthesizer**: Pure Python/NumPy/Wave synthesis of the classic *"Happy Birthday"* celesta chime melody — **zero external audio files required!** (Also auto-detects and prioritizes any custom MP3/WAV in `assets/birthday-song.mp3`).
- **Interactive Love Letter Modal 💌**: Click the *"💌 Open Love Letter"* button or press `L` to smoothly slide open Gloria's special love letter in a frosted-glass parchment card, accompanied by a magical sparkle chime.
- **Interactive Particle Fireworks & Fairy Dust**:
  - Floating hearts and rose petals with sinusoidal drift.
  - Twinkling multi-phase stars.
  - Click anywhere on screen to burst a fountain of hearts and golden star dust.
  - Subtle fairy dust cursor trail on mouse movement.
- **Flanking Fibonacci Spiral Roses**: Botanical golden-angle (137.5°) petal spirals with anti-aliased leaves and stems.
- **Interactive Music Equalizer Button**: Animated bouncing visualizer bars in the bottom-right corner to play or pause the music anytime.
- **Dual Engine Architecture**: Next-generation Pygame-CE engine by default, with preserved classic Turtle fallback (`--engine turtle`).

---

## 🚀 Quick Start

### 1. Install Dependencies
All required libraries are pre-installed in this environment. For other machines:
```bash
pip install -r requirements.txt
```

### 2. Run the Card
```bash
python gloria_birthday.py
```

### Optional Flags
```bash
# Smooth 120 FPS display
python gloria_birthday.py --fps 120

# Launch directly into Fullscreen
python gloria_birthday.py --fullscreen

# Start with music muted
python gloria_birthday.py --mute

# Custom resolution
python gloria_birthday.py --width 1200 --height 900

# Classic vintage Turtle mode
python gloria_birthday.py --engine turtle
```

---

## 🎮 Controls

| Input | Action |
| :--- | :--- |
| **Left Click** | Open Love Letter / Toggle Music / Burst Hearts anywhere |
| **Space** | Toggle Background Music on/off |
| **L** | Open / Close the Love Letter card |
| **F11** | Toggle Fullscreen mode |
| **Esc** | Close Love Letter (if open) or Exit |
