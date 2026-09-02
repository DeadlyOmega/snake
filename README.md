<div align="center">

# 🐍 Aurora Snake

**Snake, but it glows.**

A flowing aurora backdrop, a snake that slides between cells instead of snapping,
and three colour themes to lose in.

</div>

---

### ✨ What's in it

🌌 **A living background** — an aurora-inspired gradient that drifts the whole time you play.

🐍 **Smooth movement** — the snake interpolates between grid cells, so it glides rather than
teleports. The food glows.

🎨 **Three themes**, a grid size you choose, a speed you choose, and a sound toggle — all from
the settings screen, no config file.

🔊 **Tones, not samples** — the apple pickup and the crash are synthesised at runtime with
`generate_tone()`, so the whole game is one file and no assets.

🖱️ **Menus that respond** — animated buttons, a settings view that explains itself, and a
cinematic game-over overlay.

### 🚀 Play

```sh
pip install pygame
python snake_game.py
```

Python 3.9+. Arrow keys or WASD. Escape pauses.

### 🧱 How it's built

One file, ~600 lines, no assets. `Vec2` for grid maths, a `Snake` that owns its own body and
collision test, `lerp` / `lerp_color` doing all the smoothing, and a settings object that
clamps itself so a bad value can't crash the game.

---

<div align="center"><sub>Built with <a href="https://www.pygame.org/">pygame</a></sub></div>
